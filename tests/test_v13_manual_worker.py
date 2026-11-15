"""Headless manual-worker tests using an isolated fake Qt signal implementation."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

class Signal:
    def __init__(self): self.calls=[]; self.callback=None
    def emit(self,*args):
        self.calls.append(args)
        if self.callback: self.callback(*args)

class QThread:
    def __init__(self,parent=None): pass

class ManualTests(unittest.TestCase):
    def setUp(self):
        qt=types.ModuleType('PySide6')
        core=types.ModuleType('PySide6.QtCore')
        core.QThread=QThread
        core.Signal=lambda *args: Signal()
        self.old={name:sys.modules.get(name) for name in ('PySide6','PySide6.QtCore')}
        sys.modules.update({'PySide6':qt,'PySide6.QtCore':core})
        spec=importlib.util.spec_from_file_location('manual_under_test',Path(__file__).resolve().parents[1]/'scripts'/'cpx400dp_manual.py')
        self.m=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def tearDown(self):
        for k,v in self.old.items():
            if v is None: sys.modules.pop(k,None)
            else: sys.modules[k]=v

    def test_disconnect_local_is_last(self):
        class Sock:
            def settimeout(self,t): pass
            def close(self): pass
        sock=Sock(); commands=[]
        worker=self.m.ManualWorker('169.254.51.7','eth0')
        worker.connected=Signal(); worker.failed=Signal()
        worker.state_changed=Signal(); worker.finished_safe=Signal()
        worker.connected.callback=lambda x: worker.request('disconnect')
        with patch.object(self.m,'connect_psu',return_value=(sock,'169.254.51.7','eth0')), \
             patch.object(self.m,'verify_initial_snapshot',return_value=({1:(.18,1.5,1),2:(.06,1.28,1)},b'')), \
             patch.object(self.m,'send',side_effect=lambda s,cmd:commands.append(cmd)):
            worker.run()
        self.assertEqual(commands,['LOCAL'])
        self.assertIn('LOCAL sent last',worker.finished_safe.calls[0][0])

    def test_manual_voltage_verified_before_success(self):
        class Sock:
            def settimeout(self,t): pass
            def close(self): pass
        sock=Sock(); commands=[]
        worker=self.m.ManualWorker('169.254.51.7','eth0')
        worker.connected=Signal(); worker.failed=Signal()
        worker.state_changed=Signal(); worker.finished_safe=Signal()
        worker.connected.callback=lambda x: worker.request('voltage',1,3.0)
        worker.state_changed.callback=lambda states, readings: worker.request('disconnect') if readings else None
        def snap(sock,chs,pending):
            values={1:(3.0,1.5,1),2:(.06,1.28,1)}
            return {k:values[k] for k in chs},pending
        with patch.object(self.m,'connect_psu',return_value=(sock,'169.254.51.7','eth0')), \
             patch.object(self.m,'verify_initial_snapshot',return_value=({1:(.18,1.5,1),2:(.06,1.28,1)},b'')), \
             patch.object(self.m,'snapshot',side_effect=snap), \
             patch.object(self.m,'measure',return_value=([3.0,.2],b'')), \
             patch.object(self.m,'send',side_effect=lambda s,cmd:commands.append(cmd)):
            worker.run()
        self.assertEqual(commands,['V1 3.000','LOCAL'])
        self.assertEqual(worker.failed.calls,[])

if __name__=='__main__': unittest.main()
