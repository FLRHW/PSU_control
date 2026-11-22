"""Replay runner CSV cleanup records against actual GUI display methods.

This deliberately tests final_state_sent/verified/physical_output_checked:
a stale 0 V / 0 A profile readback must NOT survive a restored ON state.
No PSU connection or Qt installation is required.
"""
import ast
import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

SOURCE = (Path(__file__).resolve().parents[1] / 'scripts' / 'cpx400dp_gui.py').read_text()
FIELDS = ['utc_time', 'elapsed_s', 'event', 'scheduled_s', 'channel',
          'set_voltage_v', 'current_limit_a', 'requested_enable',
          'measured_voltage_v', 'measured_current_a', 'lateness_ms',
          'readback_duration_ms', 'note']


def extracted_method(name, ns):
    tree = ast.parse(SOURCE)
    window = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Window')
    method = next(n for n in window.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<gui>', 'exec'), ns)
    return ns[name]


def make_rows(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


class FinalDisplayTests(unittest.TestCase):
    def make_gui(self, path):
        voltage = Mock()
        restoration = Mock()
        gui = SimpleNamespace(
            readback_poll_enabled=True, measurement_log=path,
            log_offset=0, log_remainder='', log_columns=None,
            channel_labels={1:voltage}, restore_labels={1:restoration},
            final_measurement_channels=set(),
            run_targets={1:{},2:{}}, update_runner_regulation=Mock())
        gui.apply_final_measurement_event = lambda *args: self.apply(gui, *args)
        return gui, voltage, restoration

    def apply(self, gui, *args):
        ns = {}
        return extracted_method('apply_final_measurement_event', ns)(gui, *args)

    def poll(self, gui):
        ns = {'csv':csv}
        return extracted_method('poll_measurements', ns)(gui)

    def test_restored_on_shows_actual_physical_voltage_not_stale_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'recording.csv'
            make_rows(path, [
                {'event':'readback', 'channel':1,
                 'measured_voltage_v':'-0.010', 'measured_current_a':'0.000'},
                {'event':'final_state_sent', 'channel':1,
                 'set_voltage_v':'11.000', 'current_limit_a':'3.530',
                 'requested_enable':'1'},
                {'event':'final_state_verified', 'channel':1,
                 'set_voltage_v':'11.000', 'current_limit_a':'3.530',
                 'requested_enable':'1'},
                {'event':'physical_output_checked', 'channel':1,
                 'set_voltage_v':'11.000', 'measured_voltage_v':'10.986',
                 'requested_enable':'1'},
                {'event':'local_sent'}])
            gui, voltage, restore = self.make_gui(path)
            self.poll(gui)
            voltage.setText.assert_called_with(
                'Post-restore: 10.99 V measured; current not sampled')
            restore.setText.assert_called_with(
                'Restoration: VERIFIED — 11.00 V / 3.53 A limit; output ON')
            self.assertIn(1, gui.final_measurement_channels)

    def test_restored_off_does_not_claim_stale_physical_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'recording.csv'
            make_rows(path, [
                {'event':'readback', 'channel':1,
                 'measured_voltage_v':'3.000', 'measured_current_a':'.200'},
                {'event':'final_state_sent', 'channel':1,
                 'set_voltage_v':'0.000', 'current_limit_a':'.100',
                 'requested_enable':'0'},
                {'event':'final_state_verified', 'channel':1,
                 'set_voltage_v':'0.000', 'current_limit_a':'.100',
                 'requested_enable':'0'},
                {'event':'physical_output_skipped', 'channel':1,
                 'requested_enable':'0'},
                {'event':'local_sent'}])
            gui, voltage, restore = self.make_gui(path)
            self.poll(gui)
            voltage.setText.assert_called_with(
                'Final output: OFF (programmed; V/I not sampled)')
            restore.setText.assert_called_with(
                'Restoration: VERIFIED — 0.00 V / 0.10 A limit; output OFF')

    def test_error_does_not_retain_previous_profile_measurements(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'recording.csv'
            make_rows(path, [
                {'event':'readback', 'channel':1,
                 'measured_voltage_v':'1.000', 'measured_current_a':'.100'},
                {'event':'final_state_sent', 'channel':1,
                 'set_voltage_v':'6.000','current_limit_a':'1.000',
                 'requested_enable':'1'},
                {'event':'final_state_error', 'channel':1,
                 'note':'verify timeout'}])
            gui, voltage, restore = self.make_gui(path)
            self.poll(gui)
            voltage.setText.assert_called_with(
                'Final output: NOT VERIFIED — check PSU')

    def test_later_readback_never_overwrites_verified_final_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'recording.csv'
            make_rows(path, [
                {'event':'final_state_verified', 'channel':1,
                 'set_voltage_v':'11.000', 'current_limit_a':'3.530',
                 'requested_enable':'1'},
                {'event':'physical_output_checked', 'channel':1,
                 'measured_voltage_v':'10.986', 'requested_enable':'1'},
                {'event':'readback', 'channel':1,
                 'measured_voltage_v':'0.000', 'measured_current_a':'0.000'}])
            gui, voltage, _ = self.make_gui(path)
            self.poll(gui)
            voltage.setText.assert_called_with(
                'Post-restore: 10.99 V measured; current not sampled')
            self.assertEqual(gui.update_runner_regulation.call_count, 0)


if __name__ == '__main__':
    unittest.main()
