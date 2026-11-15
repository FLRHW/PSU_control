"""Qt-free GUI paused-manual transport test and guard checks."""
import ast
import json
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


class GuiPauseIPCTests(unittest.TestCase):
    def test_gui_manual_payload_sent_to_private_socket(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'scripts' / 'cpx400dp_gui.py').read_text())
        window = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name=='Window')
        fn = next(node for node in window.body if isinstance(node, ast.FunctionDef) and node.name=='send_pause_manual_command')
        ns={'json':json,'socket':socket,'OSError':OSError}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'gui manual ipc','exec'),ns)
        with tempfile.TemporaryDirectory(prefix='cpxgui-') as folder:
            path=str(Path(folder)/'ctl.sock')
            with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as listener:
                listener.bind(path)
                obj=SimpleNamespace(pause_manual_active=True, pause_socket_path=path,
                                    paused=True, manual_status=Mock(), append_console=Mock())
                ns[fn.name](obj,'voltage',1,3.25)
                raw=listener.recv(2048)
                self.assertEqual(json.loads(raw),{'action':'voltage','channel':1,'value':3.25})
                obj.manual_status.setText.assert_not_called()

    def test_ipc_disabled_outside_pause(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'scripts' / 'cpx400dp_gui.py').read_text())
        window = next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Window')
        fn = next(node for node in window.body if isinstance(node,ast.FunctionDef) and node.name=='send_pause_manual_command')
        ns={'json':json,'socket':socket}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'gui ipc','exec'),ns)
        obj=SimpleNamespace(pause_manual_active=True,pause_socket_path='/does-not-exist',paused=False)
        ns[fn.name](obj,'voltage',1,3.25)

if __name__=='__main__':unittest.main()
