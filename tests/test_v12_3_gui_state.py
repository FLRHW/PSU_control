"""GUI status-reset regression without requiring Qt in the test environment."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


class GuiResetTests(unittest.TestCase):
    def test_selection_change_clears_stale_measurements_without_psu_io(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'scripts' / 'cpx400dp_gui.py').read_text())
        klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Window')
        fn = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == 'clear_previous_run_display')
        ns = {'QProcess': SimpleNamespace(NotRunning=0)}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<gui reset>', 'exec'), ns)
        reset = ns[fn.name]
        obj = SimpleNamespace(
            running=False, process=None,
            measurement_timer=Mock(), readback_poll_enabled=True,
            measurement_log=Path('/tmp/prior_run.csv'), log_offset=999,
            log_remainder='stale', log_columns={'event': 0},
            progress=Mock(), phase_label=Mock(), run_summary='COMPLETED',
            success_summary=True, experiment_health_failed=True,
            final_states={1: True}, last_phase='Complete',
            report_path=Path('/tmp/prior_report.html'), report_btn=Mock(),
            channel_labels={1: Mock(), 2: Mock()},
            restore_labels={1: Mock(), 2: Mock()}, status=Mock(),
            set_channel_status_idle=Mock(), set_preview_progress=Mock(),
        )
        reset(obj)
        self.assertFalse(obj.readback_poll_enabled)
        self.assertIsNone(obj.measurement_log)
        self.assertEqual(obj.log_offset, 0)
        self.assertEqual(obj.final_states, {})
        self.assertIsNone(obj.report_path)
        obj.measurement_timer.stop.assert_called_once()
        obj.progress.setValue.assert_called_once_with(0)
        obj.phase_label.setText.assert_called_once_with('Phase: Idle')
        obj.set_channel_status_idle.assert_called_once_with()

    def test_never_clear_during_active_run(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'scripts' / 'cpx400dp_gui.py').read_text())
        klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Window')
        fn = next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == 'clear_previous_run_display')
        ns = {'QProcess': SimpleNamespace(NotRunning=0)}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<gui reset>', 'exec'), ns)
        obj = SimpleNamespace(running=True, process=None, measurement_timer=Mock())
        ns[fn.name](obj)
        obj.measurement_timer.stop.assert_not_called()


if __name__ == '__main__':
    unittest.main()
