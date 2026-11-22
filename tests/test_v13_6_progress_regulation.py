"""Offline visual marker and readback-derived regulation regression."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from cpx400dp_regulation_estimate import estimate_regulation
from cpx400dp_run_enhanced import load_profile, validate_schedule

GUI = (Path(__file__).resolve().parents[1]/'scripts'/'cpx400dp_gui.py').read_text()


class RegressionTests(unittest.TestCase):
    def test_mode_inference_conservative(self):
        self.assertEqual(estimate_regulation(3, 1, True, 2.99, .2), 'CV likely')
        self.assertEqual(estimate_regulation(6, .15, True, 2.25, .15), 'CC likely')
        self.assertIsNone(estimate_regulation(3, .15, False, 3, .15))
        self.assertIsNone(estimate_regulation(0, .15, True, 0, .1))
        self.assertIsNone(estimate_regulation(3, 1, True, 0.2, 0.01))
        self.assertIsNone(estimate_regulation(3, .15, True, 3, 1))
        self.assertIsNone(estimate_regulation(None, .15, True, 2, .1))
        self.assertIsNone(estimate_regulation(3, .15, None, 2, .1))
        self.assertIsNone(estimate_regulation(3, .15, True, float('nan'), .1))

    def test_gui_position_is_display_only_and_pause_frozen(self):
        self.assertIn('class ProfileProgressImage(QLabel):', GUI)
        self.assertIn('QPainter(self)', GUI)
        self.assertIn('0.105 + 0.775 * self.profile_fraction', GUI)
        self.assertIn('self.run_initial_ramp_s', GUI)
        self.assertIn('self.profile_duration_s', GUI)
        self.assertIn("not self.paused and not self.stopping", GUI)
        self.assertIn("self.last_progress_elapsed = progress['elapsed_s']", GUI)
        self.assertIn('self.set_preview_progress(1.)', GUI)
        self.assertIn('self.preview_cursor_timer.setInterval(200)', GUI)
        self.assertIn('self.update_runner_regulation(ch, v, a)', GUI)
        self.assertIn('estimate_regulation(', GUI)
        self.assertIn("REGULATION: UNKNOWN", GUI)
        self.assertNotIn("query_expected(", GUI)

    def test_qt_preview_marker_renders_without_altering_original_pixmap(self):
        try:
            from cpx400dp_gui import QApplication, QPixmap, QColor, ProfileProgressImage
        except ImportError:
            self.skipTest('Qt not installed in optional test environment')
        app = QApplication.instance() or QApplication([])
        original = QPixmap(680, 360)
        original.fill(QColor('white'))
        picture = ProfileProgressImage()
        picture.setPixmap(original)
        picture.setFixedSize(680, 360)
        picture.set_profile_fraction(.5)
        actual = picture.grab().toImage()
        x = round(680 * (.105 + .775 * .5))
        self.assertEqual(actual.pixelColor(x, 160).name(), '#a622ac')
        self.assertEqual(original.toImage().pixelColor(x,160).name(), '#ffffff')
        picture.set_profile_fraction(None)
        self.assertEqual(picture.grab().toImage().pixelColor(x,160).name(), '#ffffff')
        picture.close()

    def test_csv_setpoint_heartbeat_does_not_flicker_mode_to_unknown(self):
        import csv
        import tempfile
        from cpx400dp_regulation_estimate import estimate_regulation

        # Exercise the actual GUI poll_measurements method without Qt or PSU.
        tree = ast.parse(GUI)
        klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Window')
        node = next(n for n in klass.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'poll_measurements')
        namespace = {'csv': csv}
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<gui poll>', 'exec'),
             namespace)

        fields = ['utc_time', 'elapsed_s', 'event', 'scheduled_s', 'channel',
                  'set_voltage_v', 'current_limit_a', 'requested_enable',
                  'measured_voltage_v', 'measured_current_a', 'lateness_ms',
                  'readback_duration_ms', 'note']
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'measurements.csv'
            with path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({'event':'output_transition','channel':1,
                                 'requested_enable':1})
                writer.writerow({'event':'setpoint','channel':1,
                                 'set_voltage_v':'4.000',
                                 'current_limit_a':'.650','requested_enable':'1'})
                writer.writerow({'event':'readback','channel':1,
                                 'measured_voltage_v':'3.980',
                                 'measured_current_a':'.270'})
                # These happen every 50ms, between 250ms measured readbacks.
                for i in range(5):
                    writer.writerow({'event':'setpoint','channel':1,
                                     'set_voltage_v':'4.000',
                                     'current_limit_a':'.650',
                                     'requested_enable':'hold'})
            meter, label = Mock(), Mock()
            gui = SimpleNamespace(
                readback_poll_enabled=True, measurement_log=path,
                log_offset=0, log_remainder='', log_columns=None,
                channel_labels={1:meter}, run_targets={1:{},2:{}},
                runner_regulation_labels={1:label}, final_measurement_channels=set())
            def update(channel, voltage=None, current=None):
                target = gui.run_targets[channel]
                state = estimate_regulation(target.get('voltage'),
                                           target.get('current'),
                                           target.get('enabled'),voltage,current)
                label.setText(state or 'UNKNOWN')
            gui.update_runner_regulation = update
            namespace['poll_measurements'](gui)
            label.setText.assert_called_with('CV likely')
            self.assertEqual(gui.run_targets[1]['enabled'], True)
            self.assertEqual(gui.run_targets[1]['voltage'], 4.0)
            self.assertEqual(label.setText.call_count, 1)
            with path.open('a', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writerow({'event':'setpoint','channel':1,
                                 'set_voltage_v':'6.000',
                                 'current_limit_a':'.150','requested_enable':'hold'})
                writer.writerow({'event':'readback','channel':1,
                                 'measured_voltage_v':'2.250',
                                 'measured_current_a':'.150'})
            namespace['poll_measurements'](gui)
            label.setText.assert_called_with('CC likely')
            with path.open('a', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writerow({'event':'output_transition','channel':1,
                                 'requested_enable':'0'})
            namespace['poll_measurements'](gui)
            label.setText.assert_called_with('UNKNOWN')

    def test_release_load_demo_stays_below_resistor_rating(self):
        root = Path(__file__).resolve().parents[1]
        p = root/'profiles/examples/hardware_demo_90s_15ohm_REQUIRES_LOAD.csv'
        (host, channels, mode, interval, rb, _, points,
         restoration, initial, final, progress) = load_profile(p)
        self.assertEqual(channels, [1])
        self.assertEqual(mode, 'step')
        self.assertEqual(points[-1][0],90)
        self.assertTrue(restoration[1])
        self.assertGreaterEqual(validate_schedule(points, interval, initial, final,
                                                  any(restoration.values())), .05)
        for t, values in points:
            voltage, current_limit, enabled = values[1]
            self.assertLessEqual(voltage**2 / 15, 5)
            self.assertLessEqual(current_limit, .65)
        self.assertTrue(any(t==40 and values[1][1]==.15 for t,values in points))
        self.assertTrue(any(t==50 and values[1][1]==.65 for t,values in points))


if __name__ == '__main__':
    unittest.main()
