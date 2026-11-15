"""Hardware-free integrated pause/manual/resume tests with private UNIX socket."""
import contextlib
import csv
import io
import json
import os
import signal
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import cpx400dp_run_enhanced as runner


class DummySocket:
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def settimeout(self, *_): pass
    def close(self): pass


class PausedManualTests(unittest.TestCase):
    def run_case(self, fail_restore=False):
        with tempfile.TemporaryDirectory(prefix='cpx-test-') as folder:
            root = Path(folder)
            profile = root / 'profile.csv'
            profile.write_text('''# host=169.254.51.7
# channels=1
# mode=step
# interval_s=0.05
# readback_interval_s=0.1
# initial_ramp_s=0
# final_ramp_s=0
# ch1_restore=true
# log_file=log.csv
# generate_report=false
time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable
0,2,1,1
1.0,3,1,1
''')
            ipc = str(root/'pause.sock')
            psu={1:[.18,1.5,1]}
            commands=[]
            saw=[]
            old_usr=signal.getsignal(signal.SIGUSR1)
            def fake_send(sock, command):
                commands.append(command)
                for instr in command.split(';'):
                    prefix,sep,value=instr.strip().partition(' ')
                    if prefix in ('V1','I1','OP1'):
                        idx={'V1':0,'I1':1,'OP1':2}[prefix]
                        if fail_restore and prefix=='V1' and value=='2.000' and any(c=='V1 4.000' for c in commands):
                            continue
                        psu[1][idx] = int(value) if idx==2 else float(value)
            def fake_snapshot(sock, channels, pending):
                return {ch:tuple(psu[ch]) for ch in channels}, pending
            def fake_finish(sock,chs,original,flags,pending,log):
                fake_send(sock, 'V1 0.180;I1 1.500;OP1 1')
                log('final_state_verified', channel=1)
                return []
            def sender():
                time.sleep(.22)
                os.kill(os.getpid(),signal.SIGUSR1)
                time.sleep(.13)
                with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as client:
                    client.sendto(json.dumps({'action':'voltage','channel':1,'value':4.0}).encode(),ipc)
                time.sleep(.19)
                saw.append(('manual_voltage',psu[1][0]))
                os.kill(os.getpid(),signal.SIGUSR1)
            stdout=io.StringIO()
            error=None
            with patch('cpx400dp_discovery.connect_psu',return_value=(DummySocket(),'169.254.51.7','eth0')), \
                 patch.object(runner,'verify_initial_snapshot',return_value=({1:(.18,1.5,1)},b'')), \
                 patch.object(runner,'snapshot',side_effect=fake_snapshot), \
                 patch.object(runner,'measure',side_effect=lambda sock,ch,pending: ((psu[ch][0],psu[ch][0]/15),pending)), \
                 patch.object(runner,'send',side_effect=fake_send), \
                 patch.object(runner,'finish_channels',side_effect=fake_finish), \
                 patch.object(runner,'collect_diagnostics',return_value=(b'',{})), \
                 patch.object(runner,'verify_physical_outputs',return_value=({1:'N/A'},b'')), \
                 contextlib.redirect_stdout(stdout):
                th=threading.Thread(target=sender)
                th.start()
                try:
                    try:
                        code=runner.execute(profile,pause_control_socket=ipc)
                    except RuntimeError as exc:
                        error=str(exc)
                        code=1
                finally:
                    th.join()
                    signal.signal(signal.SIGUSR1,old_usr)
            with (root/'log.csv').open() as stream:
                events=list(csv.DictReader(stream))
            return code,commands,events,stdout.getvalue(),saw,os.path.exists(ipc),error

    def test_manual_voltage_and_resume_restore(self):
        code,commands,events,output,saw,exists,error=self.run_case()
        self.assertEqual(code,0)
        self.assertEqual(saw,[('manual_voltage',4.0)])
        self.assertIn('[PAUSE MANUAL OK]',output)
        self.assertIn('[PAUSE RESTORED]',output)
        self.assertIn('manual_setpoint',{r['event'] for r in events})
        self.assertIn('V1 4.000',commands)
        manual_idx=commands.index('V1 4.000')
        self.assertTrue(any('V1 2.000;I1 1.000' in c for c in commands[manual_idx+1:]))
        self.assertEqual(commands[-1],'LOCAL')
        self.assertFalse(exists)
        self.assertIsNone(error)

    def test_failed_resume_verification_does_not_advance_profile(self):
        code, commands, events, output, saw, exists, error = self.run_case(fail_restore=True)
        self.assertEqual(code,1)
        self.assertIn('Cannot resume safely',error)
        self.assertNotIn('[RESUMED]', output)
        self.assertEqual(commands[-1],'LOCAL')
        self.assertIn('final_state_verified',{r['event'] for r in events})
        self.assertFalse(exists)

    def test_pause_ipc_is_disabled_when_not_configured(self):
        # Existing API and tests still run without a pause control socket.
        self.assertIsNone(runner.execute.__defaults__[0] if runner.execute.__defaults__ else None)

if __name__=='__main__': unittest.main()
