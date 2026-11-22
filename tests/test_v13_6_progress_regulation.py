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
