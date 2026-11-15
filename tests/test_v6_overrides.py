"""v6 override and report tests. All offline; no PSU connection."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cpx400dp_run_enhanced as runner
from cpx400dp_preview import profile_summary
from cpx400dp_report import generate

SAMPLE=Path(__file__).resolve().parents[1] / 'profiles' / '10.csv'

class V6Tests(unittest.TestCase):
    def test_preview_uses_overrides_without_mutating_csv(self):
        before=SAMPLE.read_bytes()
        overrides={'mode':'step','interval_s':0.1,'readback_interval_s':0.2,
                   'initial_ramp_s':3.0,'final_ramp_s':4.0}
        values=profile_summary(SAMPLE,overrides=overrides)
        for key,value in overrides.items():
            self.assertEqual(values[key],value)
        self.assertEqual(SAMPLE.read_bytes(),before)
        self.assertEqual(profile_summary(SAMPLE)['mode'],'linear')

    def test_invalid_override_rejected_prior_to_connection(self):
        for overrides in ({'interval_s':0.0}, {'readback_interval_s':0.05},
                          {'initial_ramp_s':-1.}, {'mode':'bad'}):
            with self.subTest(overrides=overrides):
                with patch.object(runner.socket,'create_connection',side_effect=AssertionError('socket must not open')):
                    with self.assertRaises(ValueError):
                        runner.execute(SAMPLE,overrides=overrides)

    def test_report_keeps_pause_hold_and_wall_clock_measurements(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'paused_measurements.csv'
            def row(sec,event,channel='',**extra):
                data={k:'' for k in runner.LOG_FIELDS}
                data.update(utc_time='2026-11-14T12:00:00+00:00',elapsed_s=str(sec),event=event,channel=str(channel))
                data.update(extra)
                return data
            rows=[row(0,'snapshot',1,set_voltage_v='2',current_limit_a='1'),
                  row(0.1,'setpoint',1,set_voltage_v='3',current_limit_a='1'),
                  row(0.2,'readback',1,measured_voltage_v='3',measured_current_a='0.1'),
                  row(0.3,'pause'),
                  row(0.3,'pause_hold',1,set_voltage_v='3',current_limit_a='1'),
                  row(0.5,'readback',1,measured_voltage_v='2.9',measured_current_a='0.12'),
                  row(0.7,'readback',1,measured_voltage_v='2.8',measured_current_a='0.13'),
                  row(0.8,'resume'),
                  row(0.8,'pause_hold',1,set_voltage_v='3',current_limit_a='1'),
                  row(0.9,'setpoint',1,set_voltage_v='4',current_limit_a='1'),
                  row(1.1,'final_state_verified',1),row(1.2,'local_sent')]
            with log.open('w',newline='') as fh:
                w=csv.DictWriter(fh,fieldnames=runner.LOG_FIELDS);w.writeheader();w.writerows(rows)
            report=generate(log)
            html=report.read_text()
            self.assertIn('pause_hold',(Path(__file__).resolve().parents[1] / 'scripts' / 'cpx400dp_report.py').read_text())
            self.assertIn('"pauses":[[0.3,"pause"],[0.8,"resume"]]',html)
            self.assertIn('pause-region',html)
            self.assertIn('"vm":[[0.2,3.0],[0.5,2.9],[0.7,2.8]]',html)

if __name__=='__main__':unittest.main()
