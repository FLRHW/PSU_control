"""v11 regression tests, offline only: no live PSU connection."""
import csv
import json
import re
import tempfile
import unittest
from pathlib import Path

import cpx400dp_preview as preview
import cpx400dp_report as report
import cpx400dp_run_enhanced as runner

BASE = Path(__file__).resolve().parents[1] / 'profiles'


class V11Tests(unittest.TestCase):
    def test_classifies_down_step_as_settling(self):
        now = 10.0
        history = [(now-0.48, 7.0), (now-0.26, 6.0), (now-0.01, 5.0)]
        self.assertEqual(runner.classify_high_readback(6.13, 5.0, history, now, .25), 'settling')

    def test_classifies_excess_over_history_as_unexplained(self):
        h = [(9.8, 7), (9.95, 5)]
        self.assertEqual(runner.classify_high_readback(37.535, 5.0, h, 10, .25), 'unexplained')
        self.assertEqual(runner.classify_high_readback(8.1, 5.0, h, 10, .25), 'unexplained')

    def test_constant_voltage_excess_still_flags(self):
        history = [(8.5, 5.0), (9.8, 5.0)]
        self.assertEqual(runner.classify_high_readback(6.5, 5.0, history, 10, .25), 'unexplained')
        self.assertEqual(runner.classify_high_readback(5.4, 5.0, history, 10, .25), 'normal')

    def test_stale_history_not_excused(self):
        self.assertEqual(runner.classify_high_readback(7, 5, [(7, 9)], 10, .25), 'unexplained')

    def test_15_profile_accepted_and_caps(self):
        summary = preview.profile_summary(BASE/'15.csv')
        self.assertGreaterEqual(summary['min_scheduled_gap_s'], .05-1e-9)
        self.assertEqual(summary['duration_s'], 20)
        _, _, _, _, _, _, points, _, _, _, _ = runner.load_profile(BASE/'15.csv')
        for _, states in points:
            self.assertLessEqual(states[1][0], 9)
            self.assertLessEqual(states[2][0], 4)
        self.assertEqual(summary['enable_commands'][1][0]['command'], 'OFF')
        self.assertEqual(summary['enable_commands'][1][1], {'time_s': .50, 'command': 'ON'})

    def test_v11_report_layout_off_regions_annotations(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/'measurements.csv'
            rows = [
                dict(event='snapshot', channel='1', requested_enable='1'),
                dict(event='snapshot', channel='2', requested_enable='0'),
                dict(event='initial_ramp', channel='1', elapsed_s='.02', set_voltage_v='1'),
                dict(event='initial_ramp', channel='2', elapsed_s='.02', set_voltage_v='1'),
                dict(event='setpoint', channel='1', elapsed_s='2', set_voltage_v='2'),
                dict(event='setpoint', channel='2', elapsed_s='2', set_voltage_v='2'),
                dict(event='output_transition', channel='1', elapsed_s='2.1', requested_enable='0'),
                dict(event='output_transition', channel='1', elapsed_s='4.1', requested_enable='1'),
                dict(event='output_transition', channel='2', elapsed_s='3.1', requested_enable='1'),
                dict(event='readback', channel='1', elapsed_s='4.9', measured_voltage_v='2', measured_current_a='.1'),
                dict(event='readback', channel='2', elapsed_s='4.9', measured_voltage_v='2', measured_current_a='.002'),
                dict(event='final_ramp', channel='1', elapsed_s='5', set_voltage_v='2'),
                dict(event='final_ramp', channel='2', elapsed_s='5', set_voltage_v='2'),
                dict(event='final_state_verified', channel='1', elapsed_s='5.5'),
                dict(event='final_state_verified', channel='2', elapsed_s='5.5'),
                dict(event='diagnostic', note='initial: *STB? = 0 (raw; event registers may clear on read)'),
                dict(event='diagnostic', note='final: *STB? = 0 (raw; event registers may clear on read)'),
                dict(event='diagnostic', note='initial: LSR1? = 3 (raw; event registers may clear on read)'),
                dict(event='diagnostic', note='final: LSR1? = 1 (raw; event registers may clear on read)'),
                dict(event='settling_readback', channel='1'),
                dict(event='local_sent')
            ]
            with file.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=runner.LOG_FIELDS); writer.writeheader(); writer.writerows(rows)
            html=report.generate(file).read_text()
            match=re.search(r'<script id="plot-data" type="application/json">(.*?)</script>',html)
            self.assertIsNotNone(match)
            data=json.loads(match.group(1))
            self.assertEqual(data['1']['off_regions'], [[2.1,4.1]])
            self.assertEqual(data['2']['off_regions'], [[0.,3.1]])
            self.assertEqual([x[2] for x in data['1']['ramp_regions']], ['Ramp','Ramp'])
            self.assertIn('OFF shading does not imply instantaneous zero',html)
            self.assertIn('class:\'off-region\'',html)
            self.assertIn('annotate(pt,state===\'1\'?\'ON\':\'OFF\'',html)
            self.assertIn('<th>Initial</th><th>Final</th>',html)
            self.assertIn('<code>LSR1?</code></td><td>3</td><td>1</td>',html)
            self.assertIn('Expected-settling readbacks</small><b>1</b>',html)
            self.assertIn('Experiment health</small><b>OK</b>',html)

    def test_v11_preview_hatched_inherited_on_and_off(self):
        with tempfile.TemporaryDirectory() as td:
            html=preview.generate_preview(BASE/'15.csv',Path(td)/'preview.html').read_text()
            self.assertIn('Output-enable directives',html)
            self.assertIn('data:image/png;base64,',html)
        src=(Path(__file__).resolve().parents[1]/'scripts'/'cpx400dp_preview.py').read_text()
        self.assertIn("'HOLD (ON)'",src)
        self.assertIn("'HOLD (OFF)'",src)
        self.assertIn("'HOLD (?)'",src)
        self.assertIn("hatch='//' if source == 'HOLD'",src)

    def test_report_old_hardware_run_is_still_readable(self):
        old=Path('/mnt/data/14_measurements_20261114_213807_362578.csv')
        if old.exists():
            with tempfile.TemporaryDirectory() as td:
                target=Path(td)/'old.csv';target.write_bytes(old.read_bytes())
                html=report.generate(target).read_text()
                self.assertIn('PSU diagnostic snapshots',html)
                self.assertIn('<th>Initial</th><th>Final</th>',html)
                self.assertIn('off_regions',html)

if __name__=='__main__': unittest.main()
