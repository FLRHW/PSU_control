"""v13.6 report rendering regression tests (offline, no PSU)."""
import csv
import tempfile
import unittest
from pathlib import Path
import cpx400dp_report as report
import cpx400dp_run_enhanced as runner


class LongReportTests(unittest.TestCase):
    def test_adaptive_axes_and_viewport_extrema_in_html(self):
        with tempfile.TemporaryDirectory() as folder:
            log=Path(folder)/'measurements.csv'
            events=[
                {'event':'config','note':'mode=linear'},
                {'event':'snapshot','channel':'1','requested_enable':'1'},
                {'event':'setpoint','channel':'1','elapsed_s':'0','set_voltage_v':'2','current_limit_a':'1'},
                {'event':'setpoint','channel':'1','elapsed_s':'3600000','set_voltage_v':'4','current_limit_a':'1'},
                {'event':'readback','channel':'1','elapsed_s':'100','measured_voltage_v':'2','measured_current_a':'0.1'},
                {'event':'readback','channel':'1','elapsed_s':'100.05','measured_voltage_v':'5','measured_current_a':'0.1'},
                {'event':'readback','channel':'1','elapsed_s':'100.10','measured_voltage_v':'2','measured_current_a':'0.1'},
                {'event':'final_state_verified','channel':'1'},
                {'event':'local_sent'}]
            with log.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=runner.LOG_FIELDS)
                w.writeheader()
                w.writerows(events)
            result=report.generate(log).read_text()
            self.assertIn('function timeUnit(span)',result)
            self.assertIn('function timeLabel(seconds,span)',result)
            self.assertIn("span>=172800?[86400,'days']",result)
            self.assertIn('const bins=new Map()',result)
            self.assertIn('let maxT=1;',result)
            self.assertNotIn('Math.max(1,...allTimes',result)
            self.assertNotIn('const stride=Math.max(1,Math.ceil(valid.length/4000))',result)
            self.assertIn('3600000',result)
            self.assertIn('LOCAL command',result)
            self.assertIn('VERIFIED',result)


if __name__=='__main__':
    unittest.main()
