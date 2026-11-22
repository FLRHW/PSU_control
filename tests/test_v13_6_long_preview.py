"""v13.6 long-duration preview smoke test (offline; no PSU connection)."""
import tempfile
import unittest
from pathlib import Path

from cpx400dp_preview import generate_preview, _sample_times
from cpx400dp_run_enhanced import load_profile


class LongPreviewTests(unittest.TestCase):
    def test_1000h_profile_preview_with_50ms_interval(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'long.csv'
            p.write_text(
                'time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable\n'
                '0,1,1,0\n'
                '1800000,2,1,1\n'
                '3600000,3,1,0\n',encoding='utf-8')
            r=load_profile(p)
            self.assertEqual(r[6][-1][0], 3600000)
            self.assertEqual(len(_sample_times(r[6],3600000,'linear')),1201)
            output=generate_preview(p, output_path=Path(td)/'preview.html')
            html=output.read_text(encoding='utf-8')
            self.assertIn('Main profile: 3.6e+06 s',html)
            self.assertIn('Minimum scheduled update gap: 50.0 ms',html)
            self.assertIn('data:image/png;base64,',html)
            self.assertIn('Channel 1',html)


if __name__=='__main__':
    unittest.main()
