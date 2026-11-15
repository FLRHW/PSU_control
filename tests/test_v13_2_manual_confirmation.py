"""Ensure paused outputs bypass confirmation without bypassing SCPI verification."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


class ManualConfirmationTests(unittest.TestCase):
    @staticmethod
    def method(name):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'scripts' / 'cpx400dp_gui.py').read_text())
        window = next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Window')
        fn=next(x for x in window.body if isinstance(x,ast.FunctionDef) and x.name==name)
        return fn

    def test_paused_manual_enable_bypasses_confirmation(self):
        fn=self.method('manual_send')
        class TrapBox:
            @classmethod
            def question(cls,*args):
                raise AssertionError('confirmation must not be shown while paused')
        ns={'QMessageBox':TrapBox}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'manual_send','exec'),ns)
        obj=SimpleNamespace(manual_online=True,pause_manual_active=True,paused=True,running=True,
              stopping=False,run_channels=(1,),manual_worker=None,manual_output_states={1:False,2:False},send_pause_manual_command=Mock())
        ns['manual_send'](obj,'output',1,1)
        obj.send_pause_manual_command.assert_called_once_with('output',1,1)

    def test_standalone_enable_does_not_require_confirmation(self):
        fn=self.method('manual_send')
        class TrapBox:
            @classmethod
            def question(cls,*args):
                raise AssertionError('manual output enable must not ask for confirmation')
        ns={'QMessageBox':TrapBox}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'manual_send','exec'),ns)
        obj=SimpleNamespace(manual_online=True,pause_manual_active=False,
                            manual_worker=Mock(),manual_output_states={1:False,2:False})
        ns['manual_send'](obj,'output',1,1)
        obj.manual_worker.request.assert_called_once_with('output',1,1)

    def test_redundant_enable_is_not_sent(self):
        fn=self.method('manual_send')
        ns={}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'manual_send','exec'),ns)
        obj=SimpleNamespace(manual_online=True,pause_manual_active=False,
                            manual_worker=Mock(),manual_output_states={1:True,2:False})
        ns['manual_send'](obj,'output',1,1)
        obj.manual_worker.request.assert_not_called()

    def test_success_is_console_only(self):
        gui=(Path(__file__).resolve().parents[1] / 'scripts' / 'cpx400dp_gui.py').read_text()
        self.assertIn("elif line.startswith('[PAUSE MANUAL OK]'):",gui)
        self.assertNotIn("self.manual_status.setText(line[len('[PAUSE MANUAL OK]'):].strip())",gui)

if __name__=='__main__': unittest.main()
