"""v11.1 regression tests using recorded 15.csv hardware observations; offline only."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import contextlib
import io

import cpx400dp_run_enhanced as runner
import cpx400dp_report as report
from test_v10_features import SimulatedPSU

BASE = Path(__file__).resolve().parents[1] / 'tests' / 'fixtures'

class V111Tests(unittest.TestCase):
    def test_real_downstep_snapshot_preserved(self):
        # Real 15.csv run: previous 9 V command was >3s earlier;
        # at 7.050 s a 3 V command must anchor 9 V history anew.
        history=[(4.05,9.0)]
        previous=9.0; new=3.0; sent=7.050
        if previous>new+0.05: history.append((sent,previous))
        history.append((sent,new))
        self.assertEqual(runner.classify_high_readback(6.455,3.0,history,7.265,0.25),'settling')

    def test_true_overvoltage_is_not_excused(self):
        history=[(7.050,9.0),(7.050,3.0)]
        for measured in (12.,20.,37.535):
            self.assertEqual(runner.classify_high_readback(measured,3.,history,7.265,.25),'unexplained')

    def test_late_error_and_constant_plateau(self):
        history=[(7.050,9.0),(7.050,3.0)]
        self.assertEqual(runner.classify_high_readback(6.455,3.,history,8.3,.25),'unexplained')
        self.assertEqual(runner.classify_high_readback(6.455,3.,[(1.0,3.)],8.3,.25),'unexplained')

    def test_report_single_high_warning_not_failure(self):
        with tempfile.TemporaryDirectory() as t:
            file=Path(t)/'log.csv'
            rows=[dict(event='snapshot', channel='1', requested_enable='1'),
                  dict(event='readback',channel='1',elapsed_s='1.0',set_voltage_v='3',measured_voltage_v='6.455',measured_current_a='.3'),
                  dict(event='implausible_high_readback',channel='1',elapsed_s='1.0',note='example'),
                  dict(event='final_state_verified',channel='1'), dict(event='local_sent')]
            with file.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=runner.LOG_FIELDS);writer.writeheader();writer.writerows(rows)
            html=report.generate(file).read_text()
            self.assertIn('Experiment health</small><b>WARNING</b>',html)
            self.assertIn('Run status</small><b>COMPLETED</b>',html)

    def test_actual_hardware_log_context(self):
        logfile=Path('/mnt/data/15_measurements_20261115_081920_665321.csv')
        if not logfile.exists(): self.skipTest('No uploaded hardware recording mounted')
        with logfile.open() as f: rows=list(csv.DictReader(f))
        anomalies=[r for r in rows if r['event']=='implausible_high_readback']
        self.assertEqual(len(anomalies),1)
        self.assertAlmostEqual(float(anomalies[0]['measured_voltage_v']),6.455,places=2)
        self.assertEqual(runner.classify_high_readback(6.455,3.,[(7.05,9.),(7.05,3.)],7.265,.25),'settling')

    def test_simulator_run_still_restores_and_local_last(self):
        with tempfile.TemporaryDirectory() as t:
            td=Path(t); profile=td/'profile.csv'
            profile.write_text('''# host=169.254.51.7
# channels=1
# mode=linear
# interval_s=0.05
# readback_interval_s=0.1
# initial_ramp_s=0.1
# final_ramp_s=0.1
# ch1_restore=true
# generate_report=true
# log_file=measure.csv
time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable
0,2,1.5,hold
0.10,9,1.5,hold
0.20,3,1.5,hold
0.30,3,1.5,hold
''')
            sim=SimulatedPSU()
            with patch.object(runner.socket,'create_connection',return_value=sim), \
                 patch('cpx400dp_discovery.connect_psu', side_effect=lambda host, interface, **kw: (__import__('socket').create_connection((host,9221)), host, interface)), \
                 patch('cpx400dp_discovery.connect_on', side_effect=lambda host, interface, **kw: __import__('socket').create_connection((host,9221))),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.execute(profile,run_id='verify'),0)
            self.assertEqual(sim.commands[-1],'LOCAL')
            with (td/'measure_verify.csv').open() as f: rows=list(csv.DictReader(f))
            self.assertTrue(any(r['event']=='phase_gap_guard' for r in rows))
            self.assertTrue(any(r['event']=='final_state_verified' for r in rows))
            self.assertTrue(report.generate(td/'measure_verify.csv').exists())

if __name__=='__main__':unittest.main()
