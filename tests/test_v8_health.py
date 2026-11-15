import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cpx400dp_run_enhanced as runner
import cpx400dp_report as report

class V8HealthTests(unittest.TestCase):
    def test_near_zero_warning_only_after_three_samples(self):
        x=runner.OutputHealthMonitor()
        self.assertIsNone(x.update(2, 5, 1, 0.0, 'initial_ramp', 1))
        self.assertIsNone(x.update(2, 5, 1, 0.0, 'profile', 2))
        self.assertIsNone(x.update(2, 5, 1, 0.0, 'profile', 2.25))
        self.assertIn('CH2',x.update(2, 5, 1, 0.0, 'profile', 2.5))
        self.assertIsNone(x.update(2, 5, 1, 0.0, 'profile', 2.75))
        self.assertEqual(x.warnings, 1)
        x.update(2, 5, 1, 4.99, 'profile', 3.0)
        self.assertIsNone(x.update(2, 5, 0, 0, 'profile', 4.0))
        self.assertIsNone(x.update(2, 5, 1, 0, 'profile', 4.25))
        self.assertIsNone(x.update(2, 5, 1, 0, 'profile', 4.5))
        self.assertIn('CH2',x.update(2, 5, 1, 0, 'profile', 4.75))

    def test_check_restored_output_and_not_applicable(self):
        fake_measure=iter([((23,0.002),b''), ((26.82,0.003),b'')])
        events=[]
        with patch.object(runner, 'measure',side_effect=lambda sock,ch,p:next(fake_measure)),patch.object(runner.time,'sleep'):
            results,pending=runner.verify_physical_outputs(None,[1,2],
               {1:(0.0,1.5,0),2:(26.83,1.28,1)}, {1:True,2:True},b'',
               lambda event,**kwargs:events.append((event,kwargs)))
        self.assertTrue(results[2].startswith('MATCHED'))
        self.assertIn('N/A',results[1]); self.assertEqual(events[0][0],'physical_output_skipped'); self.assertEqual(events[1][0],'physical_output_checked')

    def test_report_shows_physical_status_and_step_mode(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'demo_measurements.csv'
            rows=[dict(event='config',channel='',note='mode=step'),
                  dict(event='setpoint',channel='2',elapsed_s='2.0',set_voltage_v='2'),
                  dict(event='setpoint',channel='2',elapsed_s='4.0',set_voltage_v='5'),
                  dict(event='readback',channel='2',elapsed_s='4.5',measured_voltage_v='4.99',measured_current_a='0.0'),
                  dict(event='final_state_verified',channel='2'),
                  dict(event='physical_output_checked',channel='2',measured_voltage_v='26.82'),
                  dict(event='local_sent',channel='')]
            with f.open('w',newline='') as out:
                writer=csv.DictWriter(out,fieldnames=runner.LOG_FIELDS);writer.writeheader();writer.writerows(rows)
            html=report.generate(f).read_text()
            self.assertIn('sampled physical output',html)
            self.assertIn('MATCHED',html)
            self.assertIn('mode',html)
            self.assertIn('"mode":"step"',html)
            self.assertIn("d.mode==='step'",html)

if __name__=='__main__':unittest.main()
