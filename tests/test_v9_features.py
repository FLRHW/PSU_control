"""v9 offline safety regression tests. No physical PSU connections."""
import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cpx400dp_run_enhanced as r
import cpx400dp_report as report


class DummySocket:
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def settimeout(self, value): pass
    def close(self): pass


class V9Tests(unittest.TestCase):
    def test_optimizer_suppresses_stable_parameters_and_does_not_send_blank(self):
        sent=[]
        opt=r.CommandOptimizer()
        with patch.object(r,'send',side_effect=lambda s,msg:sent.append(msg)):
            for vals in ({1:(2,1),2:(3,1)}, {1:(2.0001,1),2:(3,1)}, {1:(2.1,1),2:(3,1)}):
                commands, updates=opt.settings(vals)
                opt.transmit(None,commands,updates)
        self.assertEqual(sent,['V1 2.000;I1 1.000;V2 3.000;I2 1.000','V1 2.100'])
        self.assertEqual(opt.suppressed,7)
        self.assertEqual(opt.instructions,5)
        self.assertEqual(opt.groups,2)

    def test_transmission_failure_does_not_cache_unsent_setting(self):
        opt=r.CommandOptimizer()
        commands,changes=opt.settings({1:(2,1)})
        with patch.object(r,'send',side_effect=OSError('disconnected')):
            with self.assertRaises(OSError): opt.transmit(None,commands,changes)
        self.assertEqual(opt.settings({1:(2,1)})[0],commands)

    def test_50ms_minimum(self):
        text=(Path(__file__).resolve().parents[1] / 'profiles' / '10.csv').read_text()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'t.csv';path.write_text(text)
            with self.assertRaisesRegex(ValueError,'0.05'):
                r.load_profile(path,overrides={'interval_s':.04})
            self.assertEqual(r.load_profile(path,overrides={'interval_s':.05})[3],.05)

    def test_abort_restores_and_local_last(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); profile=d/'one.csv'
            profile.write_text('''# host=169.254.51.7
# channels=1
# mode=linear
# interval_s=0.05
# readback_interval_s=0.1
# initial_ramp_s=0
# final_ramp_s=0
# ch1_restore=true
# abort_on_output_fault=true
# log_file=measurements.csv
# generate_report=false
time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable
0,4,1,hold
1,6,1,hold
''')
            sent=[]
            def fake_finish(sock, channels, saved, flags, pending, log):
                sent.append('RESTORE')
                log('final_state_verified',channel=1)
                return []
            def fake_snapshot(sock, channels, pending):
                return {1:(2.27,1.5,1)},b''
            def fake_measure(sock,ch,pending):
                return (0.,0.),b''
            with patch.object(r.socket,'create_connection',return_value=DummySocket()), \
                 patch('cpx400dp_discovery.connect_psu', side_effect=lambda host, interface, **kw: (__import__('socket').create_connection((host,9221)), host, interface)), \
                 patch('cpx400dp_discovery.connect_on', side_effect=lambda host, interface, **kw: __import__('socket').create_connection((host,9221))), \
                 patch.object(r,'snapshot',side_effect=fake_snapshot), \
                 patch.object(r,'measure',side_effect=fake_measure), \
                 patch.object(r,'send',side_effect=lambda sock,cmd:sent.append(cmd)), \
                 patch.object(r,'finish_channels',side_effect=fake_finish), \
                 patch.object(r,'verify_physical_outputs',return_value=({1:'MATCHED'},b'')), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                code=r.execute(profile,run_id='offline')
            self.assertEqual(code,2)
            self.assertEqual(sent[-1],'LOCAL')
            self.assertIn('RESTORE',sent)
            with (d/'measurements_offline.csv').open() as source:
                records=list(csv.DictReader(source))
            events={row['event'] for row in records}
            self.assertIn('output_health_warning',events)
            self.assertIn('output_fault_abort',events)
            self.assertIn('final_state_verified',events)
            self.assertIn('command_summary',events)
            self.assertIn('ABORTED (output fault)',output.getvalue())
            self.assertIn('ABORTED (OUTPUT FAULT)', report.generate(d/'measurements_offline.csv').read_text())

    def test_report_power_default_health_and_transitions(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'test_measurements.csv'
            events=[
                dict(event='config',note='mode=linear'),
                dict(event='setpoint',elapsed_s='0.1',channel='1',set_voltage_v='2.000'),
                dict(event='output_transition',elapsed_s='0.1',channel='1',requested_enable='1'),
                dict(event='readback',elapsed_s='0.15',channel='1',measured_voltage_v='37.535',measured_current_a='0.5'),
                dict(event='implausible_high_readback',elapsed_s='0.15',channel='1'),
                dict(event='final_state_verified',channel='1'),
                dict(event='local_sent')]
            with path.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=r.LOG_FIELDS);w.writeheader();w.writerows(events)
            html=report.generate(path).read_text()
            self.assertIn('data-key="p" checked',html)
            self.assertIn('Unexplained high readbacks',html)
            self.assertIn('Experiment health',html)
            self.assertIn('"transitions":[[0.1,"1"]]',html)
            self.assertIn("?'ON':'OFF'",html)

if __name__ == '__main__': unittest.main()
