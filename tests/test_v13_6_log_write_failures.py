"""Fault-injection safety regression for measurement CSV write failures.

No hardware sockets, system networking changes, or PSU commands.
"""
import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cpx400dp_run_enhanced as runner


class DummySocket:
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def settimeout(self, *_): pass
    def close(self): pass


class WriteFailureTests(unittest.TestCase):
    def _exercise_failure(self, failing_event):
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder) / 'fault_profile.csv'
            profile.write_text('''# host=192.168.71.2
# channels=1
# mode=step
# interval_s=0.05
# readback_interval_s=0.1
# ch1_restore=true
# initial_ramp_s=0
# final_ramp_s=0
# log_file=fault_measurements.csv
# generate_report=false
time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable
0,0.5,0.1,0
0.1,0.5,0.1,0
''')
            send_commands = []
            logs_written = []
            original_writer = csv.DictWriter

            class BrokenWriter:
                def __init__(self, stream, fieldnames):
                    self.original = original_writer(stream, fieldnames=fieldnames)
                    self.failed = False

                def writeheader(self):
                    return self.original.writeheader()

                def writerow(self, row):
                    event = row.get('event')
                    if event == failing_event and not self.failed:
                        self.failed = True
                        raise OSError('simulated ENOSPC in ' + event)
                    logs_written.append(event)
                    return self.original.writerow(row)

            def fake_finish(sock, channels, states, flags, pending, log):
                send_commands.append('RESTORED')
                log('final_state_verified', channel=1)
                return []

            output = io.StringIO()
            stderr = io.StringIO()
            with patch('cpx400dp_discovery.connect_psu',
                       return_value=(DummySocket(), '192.168.71.2', 'eth0')), \\
                 patch.object(runner, 'verify_initial_snapshot',
                              return_value=({1:(0.0,0.1,0)}, b'')), \\
                 patch.object(runner, 'measure', return_value=((0.0,0.0), b'')), \\
                 patch.object(runner, 'send',
                              side_effect=lambda sock, cmd: send_commands.append(cmd)), \\
                 patch.object(runner, 'finish_channels', side_effect=fake_finish), \\
                 patch.object(runner, 'collect_diagnostics', return_value=(b'', {})), \\
                 patch.object(runner, 'verify_physical_outputs',
                              return_value=({1:'NOT CHECKED'}, b'')), \\
                 patch.object(runner.csv, 'DictWriter', BrokenWriter), \\
                 contextlib.redirect_stdout(output), contextlib.redirect_stderr(stderr):
                with self.assertRaises(runner.RecordingWriteFailure):
                    runner.execute(profile, run_id='offline', psu_ip='192.168.71.2')
            self.assertIn('RESTORED', send_commands)
            self.assertEqual(send_commands[-1], 'LOCAL')
            self.assertEqual(stderr.getvalue().count('[RECORDING WRITE FAILURE]'), 1)
            self.assertIn('recording incomplete', output.getvalue().lower())
            self.assertEqual(sum(x == failing_event for x in logs_written), 0)

    def test_active_setpoint_write_failure_preserves_restore_and_local(self):
        self._exercise_failure('setpoint')

    def test_cleanup_verification_write_failure_still_sends_local(self):
        self._exercise_failure('final_state_verified')

    def test_failure_at_last_post_local_write_does_not_report_success(self):
        self._exercise_failure('command_summary')

    def test_main_report_check_is_streamed(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] /
                  'scripts' / 'cpx400dp_run_enhanced.py').read_text()
        self.assertIn("any(row.get('event') == 'readback' for row in csv.DictReader(f))", source)
        self.assertNotIn('events = list(csv.DictReader(f))', source)


if __name__ == '__main__':
    unittest.main()
