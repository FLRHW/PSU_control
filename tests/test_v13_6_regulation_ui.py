"""v13.6 regulation badge and paused transport regression checks (offline)."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

SOURCE=(Path(__file__).resolve().parents[1]/'scripts'/'cpx400dp_gui.py').read_text()
RUNNER=(Path(__file__).resolve().parents[1]/'scripts'/'cpx400dp_run_enhanced.py').read_text()
WORKER=(Path(__file__).resolve().parents[1]/'scripts'/'cpx400dp_manual.py').read_text()


def method(name):
    tree=ast.parse(SOURCE)
    window=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Window')
    return next(n for n in window.body if isinstance(n,ast.FunctionDef) and n.name==name)


class RegulationUiTests(unittest.TestCase):
    def test_mode_label_is_explicitly_last_event(self):
        fn=method('manual_regulation_update')
        scope={}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'manual_regulation_update','exec'),scope)
        cv,cc=Mock(),Mock()
        ui=SimpleNamespace(manual_cards={(1,'regulation'):cv,(2,'regulation'):cc})
        scope['manual_regulation_update'](ui,{1:'CV',2:'CC'})
        cv.setText.assert_called_with('REGULATION: CV (last event)')
        cc.setText.assert_called_with('REGULATION: CC (last event)')
        scope['manual_regulation_update'](ui,{1:None,2:'UNREG'})
        cv.setText.assert_called_with('REGULATION: UNKNOWN')
        cc.setText.assert_called_with('REGULATION: UNREG (last event)')

    def test_manual_worker_reuses_existing_connection(self):
        self.assertIn('regulation_changed = pyqtSignal(object)',WORKER)
        self.assertIn("query_expected(\n                                sock, f'LSR{channel}?'",WORKER)
        self.assertIn('self.regulation_changed.emit(regulation)',WORKER)

    def test_paused_mode_only_uses_runner_owned_socket(self):
        self.assertIn('def poll_paused_regulation(sock, pending):',RUNNER)
        self.assertIn("sock, f'LSR{ch}?'",RUNNER)
        self.assertIn("'regulation': pause_limit_modes[ch]",RUNNER)
        self.assertIn("self.manual_regulation_update(modes)",SOURCE)


if __name__=='__main__':
    unittest.main()
