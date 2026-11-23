"""No instrument access: validate GUI-facing channel selection and preview ticks."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cpx400dp_run_enhanced import load_profile
from cpx400dp_preview import profile_summary, generate_preview

HERE = Path(__file__).resolve().parents[1] / 'tests' / 'fixtures'


class ChannelOverrideTests(unittest.TestCase):
    def test_select_subset_from_two_channel_csv(self):
        orig = load_profile(HERE / '15.csv')
        self.assertEqual(orig[1], [1, 2])
        for requested in ('1', '2'):
            result = load_profile(HERE / '15.csv', overrides={'channels': requested})
            self.assertEqual(result[1], [int(requested)])
            self.assertEqual(set(result[7]), {int(requested)})
            self.assertTrue(all(set(pts.keys()) == {int(requested)} for _, pts in result[6]))
            self.assertEqual(profile_summary(HERE / '15.csv', overrides={'channels': requested})['channels'], [int(requested)])
        self.assertEqual(load_profile(HERE / '15.csv')[1], [1, 2])

    def test_subset_cannot_enable_absent_channel(self):
        fixture = HERE / '17_irregular_setpoint_spacing.csv'
        if not fixture.exists():
            self.skipTest('Optional profile 17 fixture not bundled')
        with self.assertRaisesRegex(ValueError, 'missing from'):
            load_profile(fixture, overrides={'channels': '1,2'})
        with self.assertRaisesRegex(ValueError, 'at least one'):
            load_profile(fixture, overrides={'channels': ''})

    def test_main_time_axis_has_numeric_ticks(self):
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib.figure import Figure
        original = Figure.savefig
        collected = []
        def inspect(fig, *args, **kwargs):
            axes = fig.axes
            self.assertEqual(len(axes), 3)
            bottom_ticks = axes[0].get_xticks()
            self.assertGreater(len(bottom_ticks), 1)
            labels = [x.get_text() for x in axes[0].get_xticklabels()]
            self.assertTrue(any(label.strip() for label in labels), labels)
            collected.append(labels)
            return original(fig, *args, **kwargs)
        with tempfile.TemporaryDirectory() as d:
            with patch.object(Figure, 'savefig', inspect):
                generate_preview(HERE / '15.csv', output_path=Path(d) / 'preview.html')
        self.assertEqual(len(collected), 2)


if __name__ == '__main__':
    unittest.main()
