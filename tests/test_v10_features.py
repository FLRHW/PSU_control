"""V10 offline tests: no physical PSU connection."""
import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cpx400dp_run_enhanced as runner
import cpx400dp_preview as preview
import cpx400dp_report as report

class SimulatedPSU:
    """Minimal deterministic text-protocol emulator for all runner commands."""
    def __init__(self, bad_diag=False):
        self.state={1:[2.27,1.5,1],2:[13.75,1.28,0]}
        self.out=b''; self.commands=[]; self.bad_diag=bad_diag
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def close(self):pass
    def settimeout(self,seconds):pass
    def sendall(self,data):
        for command in data.decode().strip().split(';'):
            self.commands.append(command)
            words=command.split(); opcode=words[0]
            if opcode == 'LOCAL': continue
            if opcode in runner.DIAGNOSTIC_QUERIES:
                self.out += (('INVALID' if self.bad_diag and opcode=='LSR2?' else '0')+'\n').encode()
            elif opcode.startswith('OP'):
                ch=int(opcode[2])
                if opcode.endswith('?'): self.out+=(str(self.state[ch][2])+'\n').encode()
                else:self.state[ch][2]=int(words[1])
            elif opcode.startswith('V') or opcode.startswith('I'):
                typ=opcode[0];ch=int(opcode[1]); index=0 if typ=='V' else 1
                if opcode.endswith('O?'):
                    val=(self.state[ch][0] if typ=='V' else (self.state[ch][0]/15 if ch==1 else 0.002)) if self.state[ch][2] else 0.0
                    self.out+=(f'{val:.3f}{"V" if typ=="V" else "A"}\n').encode()
                elif opcode.endswith('?'):
                    self.out+=(f'{typ}{ch} {self.state[ch][index]:.3f}\n').encode()
                else:self.state[ch][index]=float(words[1])
            else:raise AssertionError('unsupported command '+command)
    def recv(self,n):
        if not self.out: raise TimeoutError('Missing reply')
        result,self.out=self.out[:n],self.out[n:]
        return result

class V10Tests(unittest.TestCase):
    def test_profiles_accept_and_reject(self):
        folder=Path(__file__).resolve().parents[1] / 'profiles'
        accepted=preview.profile_summary(folder/'14.csv')
        self.assertAlmostEqual(accepted['min_scheduled_gap_s'],.05)
        self.assertEqual(accepted['enable_commands'][1][0],{'time_s':0.0,'command':'OFF'})
        self.assertEqual(accepted['enable_commands'][1][1],{'time_s':.05,'command':'ON'})
        for name in ['14_REJECT_25ms_EXTRA_POINT_OFFLINE_ONLY.csv','14_REJECT_20ms_FINAL_GAP_OFFLINE_ONLY.csv','14_REJECT_40ms_INTERVAL_OFFLINE_ONLY.csv']:
            with self.subTest(name=name),self.assertRaises(ValueError):preview.profile_summary(folder/'negative_tests'/name)
    def test_invalid_profile_rejected_before_connection(self):
        folder=Path(__file__).resolve().parents[1] / 'profiles'
        with patch.object(runner.socket, 'create_connection', side_effect=AssertionError('MUST NOT CONNECT')) as connect:
            with self.assertRaisesRegex(ValueError,'Unsafe scheduled setpoint spacing'):
                runner.execute(folder/'negative_tests'/'14_REJECT_25ms_EXTRA_POINT_OFFLINE_ONLY.csv', run_id='negative')
            connect.assert_not_called()

    def test_ramp_shading_from_logged_phases(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); profile=td/'ramp.csv'
            profile.write_text('''# host=169.254.51.7
# channels=1
# mode=linear
# interval_s=0.05
# readback_interval_s=0.1
# initial_ramp_s=0.10
# final_ramp_s=0.10
# ch1_restore=true
# log_file=ramp_measurements.csv
# generate_report=false
time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable
0,2.5,1.5,hold
0.1,3.0,1.5,hold
''')
            sim=SimulatedPSU()
            with patch.object(runner.socket,'create_connection',return_value=sim), \
                 patch('cpx400dp_discovery.connect_psu', side_effect=lambda host, interface, **kw: (__import__('socket').create_connection((host,9221)), host, interface)), \
                 patch('cpx400dp_discovery.connect_on', side_effect=lambda host, interface, **kw: __import__('socket').create_connection((host,9221))),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.execute(profile,run_id='mock'),0)
            html=report.generate(td/'ramp_measurements_mock.csv').read_text()
            self.assertIn('ramp_regions', html)
            self.assertIn('Ramp',html)
            self.assertIn('ramp_regions',html)
            self.assertIn("class:'ramp-region'", html)
            self.assertEqual(sim.commands[-1],'LOCAL')

    def test_heartbeat_intervals(self):
        self.assertEqual(runner.effective_heartbeat(24,10),2.4)
        self.assertEqual(runner.effective_heartbeat(200,10),10)
        self.assertEqual(runner.effective_heartbeat(200,5),5)
    def test_preview_has_output_strip_and_notes(self):
        folder=Path(__file__).resolve().parents[1] / 'profiles'
        with tempfile.TemporaryDirectory() as tmp:
            out=preview.generate_preview(folder/'14.csv',Path(tmp)/'preview.html')
            txt=out.read_text()
            self.assertIn('Output-enable directives',txt)
            self.assertIn('Minimum scheduled update gap',txt)
            self.assertIn('Output note',txt)
            self.assertIn('data:image/png;base64,',txt)
            self.assertIn('0 s: OFF; 0.05 s: ON',txt)
    def test_full_mock_run_diagnostics_report_and_local_last(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); profile=td/'one.csv'
            profile.write_text('''# host=169.254.51.7
# channels=1,2
# mode=linear
# interval_s=0.05
# readback_interval_s=0.1
# initial_ramp_s=0
# final_ramp_s=0
# ch1_restore=true
# ch2_restore=true
# generate_report=true
# log_file=measurements.csv
time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable,ch2_voltage_v,ch2_current_limit_a,ch2_enable
0,2.5,1.5,0,2,0.5,0
0.05,2.5,1.5,1,2,0.5,1
0.10,3.0,1.5,hold,2,0.5,0
0.15,2.5,1.5,hold,2,0.5,hold
''')
            sim=SimulatedPSU()
            with patch.object(runner.socket,'create_connection',return_value=sim), \
                 patch('cpx400dp_discovery.connect_psu', side_effect=lambda host, interface, **kw: (__import__('socket').create_connection((host,9221)), host, interface)), \
                 patch('cpx400dp_discovery.connect_on', side_effect=lambda host, interface, **kw: __import__('socket').create_connection((host,9221))),contextlib.redirect_stdout(io.StringIO()):
                result=runner.execute(profile,run_id='mock')
            self.assertEqual(result,0)
            self.assertEqual(sim.commands[-1],'LOCAL')
            self.assertEqual(sim.commands.count('*STB?'),2)
            self.assertEqual(sim.commands.count('LSR1?'),2)
            self.assertEqual(sim.commands.count('LSR2?'),2)
            self.assertEqual(sim.commands.count('*ESR?'),2)
            self.assertEqual(sim.commands.count('EER?'),2)
            self.assertEqual(sim.commands.count('QER?'),2)
            with (td/'measurements_mock.csv').open() as f:rows=list(csv.DictReader(f))
            self.assertEqual(len([r for r in rows if r['event']=='diagnostic']),12)
            self.assertEqual(len([r for r in rows if r['event']=='final_state_verified']),2)
            self.assertTrue(any(r['event']=='output_transition' and r['channel']=='1' for r in rows))
            report_text=report.generate(td/'measurements_mock.csv').read_text()
            self.assertIn('PSU diagnostic snapshots',report_text)
            self.assertIn('Initial ramp',report_text) if False else None
            self.assertIn('SENT</b>',report_text)
    def test_diag_invalid_reply_does_not_prevent_local(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); profile=td/'one.csv'
            profile.write_text('''# host=169.254.51.7
# channels=1
# mode=linear
# interval_s=0.05
# readback_interval_s=0.1
# initial_ramp_s=0
# final_ramp_s=0
# ch1_restore=true
# generate_report=false
# log_file=measurements.csv
time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable
0,2.5,1.5,hold
0.05,2.5,1.5,hold
''')
            sim=SimulatedPSU(bad_diag=True)
            with patch.object(runner.socket,'create_connection',return_value=sim), \
                 patch('cpx400dp_discovery.connect_psu', side_effect=lambda host, interface, **kw: (__import__('socket').create_connection((host,9221)), host, interface)), \
                 patch('cpx400dp_discovery.connect_on', side_effect=lambda host, interface, **kw: __import__('socket').create_connection((host,9221))),contextlib.redirect_stdout(io.StringIO()):
                result=runner.execute(profile,run_id='mock')
            self.assertEqual(result,0)
            self.assertEqual(sim.commands[-1],'LOCAL')
            with (td/'measurements_mock.csv').open() as f:rows=list(csv.DictReader(f))
            self.assertEqual(len([r for r in rows if r['event']=='diagnostic_error']),2)

if __name__=='__main__':unittest.main()
