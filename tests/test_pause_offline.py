"""Offline controlled pause/resume/stop tests; never open instrument sockets."""
import contextlib
import csv
import io
import os
import signal
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
    def settimeout(self, timeout): pass
    def close(self): pass

class PauseOfflineTests(unittest.TestCase):
    def run_mocked(self, interrupt=False):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            profile=root/'test.csv'
            profile.write_text('''# host=169.254.51.7
# channels=1
# mode=linear
# interval_s=0.05
# readback_interval_s=0.15
# initial_ramp_s=0.10
# final_ramp_s=0.10
# ch1_restore=true
# log_file=measurements.csv
# generate_report=false
time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable
0,2,1,hold
0.7,3,1,hold
''')
            commands=[]
            def fake_send(sock, command): commands.append((time.monotonic(), command))
            def fake_finish(sock, channels, original, flags, pending, log):
                log('final_state_verified', channel=1, note='dummy verified')
                return []
            def sender():
                time.sleep(0.22)
                os.kill(os.getpid(), signal.SIGUSR1)
                if interrupt:
                    time.sleep(0.25)
                    os.kill(os.getpid(), signal.SIGINT)
                else:
                    time.sleep(0.42)
                    os.kill(os.getpid(), signal.SIGUSR1)
            buf=io.StringIO()
            previous = signal.getsignal(signal.SIGUSR1)
            with patch.object(runner.socket, 'create_connection', return_value=DummySocket()), \
                 patch('cpx400dp_discovery.connect_psu', side_effect=lambda host, interface, **kw: (__import__('socket').create_connection((host,9221)), host, interface)), \
                 patch('cpx400dp_discovery.connect_on', side_effect=lambda host, interface, **kw: __import__('socket').create_connection((host,9221))), \
                 patch.object(runner, 'snapshot', return_value=({1:(2.0,1.0,1)},b'')), \
                 patch.object(runner, 'send', fake_send), \
                 patch.object(runner, 'measure', return_value=((2.0,0.1),b'')), \
                 patch.object(runner, 'query_expected', return_value=('1',b'')), \
                 patch.object(runner,'finish_channels',fake_finish), \
                 contextlib.redirect_stdout(buf):
                t0=time.monotonic()
                th=threading.Thread(target=sender)
                th.start()
                try:
                    result=runner.execute(profile)
                finally:
                    th.join()
                    signal.signal(signal.SIGUSR1, previous)
            with (root/'measurements.csv').open() as fh:
                rows=list(csv.DictReader(fh))
            return result, time.monotonic()-t0, rows, commands, buf.getvalue()

    def test_pause_freezes_profile_then_resumes(self):
        status, duration, rows, commands, output = self.run_mocked(False)
        self.assertEqual(status,0)
        self.assertIn('[PAUSED]',output)
        self.assertIn('[RESUMED]',output)
        self.assertGreater(duration,1.25)
        self.assertLess(duration,2.5)
        pause=next(float(r['elapsed_s']) for r in rows if r['event']=='pause')
        resume=next(float(r['elapsed_s']) for r in rows if r['event']=='resume')
        self.assertGreater(resume-pause,0.38)
        paused_reads = [r for r in rows if r['event']=='readback'
                        and r.get('note') == 'phase=paused']
        self.assertGreaterEqual(len(paused_reads), 2,
                                'Readbacks must continue throughout Pause')
        paused_profile_times = [float(r['scheduled_s']) for r in paused_reads]
        self.assertLess(max(paused_profile_times)-min(paused_profile_times), 0.02)
        paused_wall_times = [float(r['elapsed_s']) for r in paused_reads]
        self.assertGreater(max(paused_wall_times)-min(paused_wall_times), 0.14)
        self.assertGreaterEqual(len([r for r in rows if r['event']=='pause_hold']),2)
        controlled=[(t,c) for t,c in commands if c != 'LOCAL']
        self.assertFalse(any(pause-0.04 < t-commands[0][0] < resume-0.05 for t,c in controlled))
        self.assertIn('final_state_verified', {r['event'] for r in rows})
        latenesses=[float(r['lateness_ms']) for r in rows if r['event']=='setpoint']
        self.assertLess(max(latenesses), 30.0)

    def test_stop_while_paused_runs_cleanup(self):
        status,duration,rows,commands,output=self.run_mocked(True)
        self.assertEqual(status,130)
        self.assertIn('Interrupted by Ctrl+C',output)
        self.assertEqual(commands[-1][1],'LOCAL')
        self.assertIn('final_state_verified',{r['event'] for r in rows})

if __name__=='__main__': unittest.main()
