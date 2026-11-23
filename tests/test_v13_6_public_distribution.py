"""Validate public README assets and portable waveform-only examples."""
import re
import unittest
from pathlib import Path

from cpx400dp_run_enhanced import load_profile

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = {
    'ch1_90s_3v.csv': (90, [1], 3),
    'ch1_90s_8v_cc.csv': (90, [1], 8),
    'dual_90s.csv': (90, [1, 2], 4),
    'ch1_24h.csv': (86400, [1], 2),
    'dual_7d.csv': (604800, [1, 2], 3),
    'dual_1000h.csv': (3600000, [1, 2], 2),
}


class PublicDistributionTests(unittest.TestCase):
    def test_only_public_samples_are_in_profiles(self):
        self.assertEqual({p.name for p in (ROOT/'profiles').iterdir()},
                         {'README.md', 'examples'})
        self.assertEqual({p.name for p in (ROOT/'profiles/examples').iterdir()},
                         {'README.md'} | set(EXAMPLES))

    def test_samples_are_waveform_only_and_parse(self):
        for name, (duration, channels, peak) in EXAMPLES.items():
            with self.subTest(name=name):
                path = ROOT/'profiles/examples'/name
                source = path.read_text()
                self.assertTrue(source.startswith('time_s,'))
                self.assertNotIn('# host=', source)
                self.assertNotIn('192.168.', source)
                self.assertNotIn('_REQUIRES_LOAD', name)
                details = load_profile(path)
                self.assertEqual(details[1], channels)
                self.assertEqual(details[6][-1][0], duration)
                self.assertEqual(max(v[0] for _, by_ch in details[6]
                                     for v in by_ch.values()), peak)

    def test_readme_has_real_images_and_one_safety_section(self):
        readme = (ROOT/'README.md').read_text()
        self.assertNotIn('![CPX400DP application icon]', readme)
        self.assertNotIn('PROJECT_HANDOVER', readme)
        self.assertNotIn('SESSION_STATE', readme)
        self.assertNotIn('RELEASE_CANDIDATE', readme)
        self.assertNotIn('Dell D6000', readme)
        self.assertNotIn('## Offline regression', readme)
        self.assertNotIn('## Version history', readme)
        self.assertNotIn('## Release screenshots', readme)
        self.assertEqual(readme.count('## Safety and responsibility'), 1)
        images = set(re.findall(r'docs/screenshots/[^)]+?\.png', readme))
        self.assertGreaterEqual(len(images), 6)
        for path in images:
            with self.subTest(path=path):
                png = ROOT/path
                self.assertTrue(png.is_file())
                self.assertTrue(png.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))


if __name__ == '__main__':
    unittest.main()
