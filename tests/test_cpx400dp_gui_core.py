import tempfile
import unittest
from pathlib import Path
from cpx400dp_gui_core import (require_files, resolve_output, embedded_preview_plots,
                              parse_progress, parse_report_path, parse_heartbeat,
                              parse_final_verification, classify_run)


class GUICoreTests(unittest.TestCase):
    def test_progress(self):
        line = '[PROGRESS] 10.0/12.0s (~2.0s remaining) | profile | ch1: 3.4 V'
        result = parse_progress(line)
        self.assertEqual(result['percent'], 83)
        self.assertEqual(result['remaining_s'], 2)
        self.assertIsNone(parse_progress('Running final ramp...'))

    def test_heartbeat_measurements_and_phase(self):
        line = ('[PROGRESS] 10.0/24.0s (~14.0s remaining) | profile | '
                'ch1: 3.386 V, 0.237 A | ch2: 2.399 V, 0.003 A | '
                'readbacks 80 OK/0 failed | max lateness 0.902 ms')
        result = parse_heartbeat(line)
        self.assertEqual(result['phase'], 'profile')
        self.assertEqual(result['readings'][1], {'voltage_v': 3.386, 'current_a': 0.237})
        self.assertEqual(result['readings'][2], {'voltage_v': 2.399, 'current_a': 0.003})
        self.assertEqual(result['percent'], 42)

    def test_restoration_and_exit_status(self):
        text = 'Channel 2 final state (original settings): VERIFIED'
        self.assertEqual(parse_final_verification(text), (2, True))
        self.assertEqual(parse_final_verification('a progress message'), None)
        self.assertEqual(classify_run(130, 'INTERRUPTED — cleanup verified', {1:True,2:True})[0], 'stopped')
        self.assertEqual(classify_run(0, 'COMPLETED — cleanup verified', {1:True})[0], 'completed')
        self.assertEqual(classify_run(130, 'INTERRUPTED — cleanup verified', {1:False})[0], 'error')
        self.assertEqual(classify_run(1, 'ERROR — cleanup not fully verified', {1:True})[0], 'error')

    def test_report_path(self):
        self.assertEqual(parse_report_path('HTML report: new_report.html', '/tmp'),
                         Path('/tmp/new_report.html'))
        self.assertIsNone(parse_report_path('Run status: COMPLETED', '/tmp'))

    def test_output_paths(self):
        self.assertEqual(resolve_output('x.html', '/tmp'), Path('/tmp/x.html'))
        self.assertEqual(resolve_output('/other/x.html', '/tmp'), Path('/other/x.html'))

    def test_dependency_check(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError) as ex:
                require_files(directory)
            self.assertIn('cpx400dp_run_enhanced.py', str(ex.exception))

    def test_embedded_plot_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            html = Path(directory) / 'test.html'
            html.write_text('<img alt="Channel 1" src="data:image/png;base64,aGVsbG8=">')
            self.assertEqual(embedded_preview_plots(html), [('Channel 1', b'hello')])


if __name__ == '__main__':
    unittest.main()
