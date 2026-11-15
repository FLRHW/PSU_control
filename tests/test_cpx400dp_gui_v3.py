"""Offline regression tests for output selection and phase notifications."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cpx400dp_run_enhanced as runner
from cpx400dp_gui_core import parse_heartbeat, parse_report_path

SAMPLE = Path(__file__).resolve().parents[1] / 'profiles' / '10.csv'

class Version3Tests(unittest.TestCase):
    def test_selected_directory_passed_to_runner_without_psu(self):
        with tempfile.TemporaryDirectory() as folder:
            seen = []
            def fake_execute(profile, output_dir=None, overrides=None, run_id=None):
                seen.append((profile, output_dir))
                return 0
            with patch.object(runner, 'execute', fake_execute), \
                 patch.object(runner, 'report_options', lambda _: {'generate_report': 'false'}), \
                 patch('sys.argv', ['runner', str(SAMPLE), '--output-dir', folder]):
                self.assertEqual(runner.main(), 0)
            self.assertEqual(seen, [(SAMPLE.resolve(), Path(folder))])

    def test_invalid_directory_fails_before_psu(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = str(Path(folder) / 'missing')
            with patch.object(runner, 'execute', side_effect=AssertionError('PSU must not be reached')), \
                 patch('sys.argv', ['runner', str(SAMPLE), '--output-dir', missing]), \
                 contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main(), 1)

    def test_cli_default_passes_no_override(self):
        got = []
        def fake_execute(profile, output_dir=None, overrides=None, run_id=None):
            got.append(output_dir)
            return 0
        with patch.object(runner, 'execute', fake_execute), \
             patch.object(runner, 'report_options', lambda _: {'generate_report': 'false'}), \
             patch('sys.argv', ['runner', str(SAMPLE)]):
            self.assertEqual(runner.main(), 0)
        self.assertEqual(got, [None])

    def test_forced_phase_heartbeat_parses(self):
        for phase in ('initial_ramp', 'profile', 'final_ramp', 'restoration'):
            line = (f'[PROGRESS] 2.0/24.0s (~22.0s remaining) | {phase} | '
                    'ch1: 2.270 V, 0.150 A | readbacks 7 OK/0 failed | max lateness 0.5 ms')
            self.assertEqual(parse_heartbeat(line)['phase'], phase)

    def test_report_absolute_location_is_preserved(self):
        self.assertEqual(parse_report_path('HTML report: /tmp/x_report.html', '/unused'),
                         Path('/tmp/x_report.html'))

if __name__ == '__main__':
    unittest.main()
