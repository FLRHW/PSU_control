"""Offline validation of shipped long-duration preview examples."""
import unittest
from pathlib import Path

from cpx400dp_run_enhanced import load_profile, validate_schedule

ROOT = Path(__file__).resolve().parents[1] / 'profiles' / 'examples'


class LongExampleTests(unittest.TestCase):
    def test_release_preview_stays_off_and_hardware_demo_is_current_limited(self):
        preview = load_profile(ROOT / 'release_demo_90s_preview.csv')
        self.assertEqual(preview[6][-1][0], 90)
        self.assertEqual(preview[1], [1, 2])
        self.assertTrue(all(v[2] == 0 for _, rows in preview[6]
                            for v in rows.values()))
        hardware = load_profile(ROOT / 'hardware_demo_90s_REQUIRES_LOAD.csv')
        self.assertEqual(hardware[1], [1])
        self.assertEqual(hardware[6][-1][0], 90)
        self.assertTrue(hardware[7][1])
        self.assertTrue(any(v[2] == 1 for _, rows in hardware[6]
                            for v in rows.values()))
        self.assertTrue(all(v[0] <= 3 and v[1] <= .1 for _, rows in hardware[6]
                            for v in rows.values()))
        self.assertEqual(hardware[6][-1][1][1][2], 0)
        for details in (preview, hardware):
            self.assertGreaterEqual(validate_schedule(details[6], details[3],
                                                      details[8], details[9], True), .05)

    def test_sparse_examples_parse_and_keep_all_outputs_disabled(self):
        for filename, total, count, channels in (
            ('long_24h_step_preview.csv', 86400, 5, [1]),
            ('long_7d_linear_preview.csv', 604800, 8, [1, 2]),
            ('long_1000h_sparse_preview.csv', 3600000, 11, [1, 2]),
        ):
            with self.subTest(filename=filename):
                (host, active, mode, interval, rb_interval, log_path,
                 points, restore, ramp_start, ramp_end, progress) = load_profile(ROOT / filename)
                self.assertEqual(host, '192.168.71.2')
                self.assertEqual(active, channels)
                self.assertEqual(points[-1][0], total)
                self.assertEqual(len(points), count)
                self.assertTrue(all(restore.values()))
                self.assertTrue(all(value[2] == 0
                                    for _, values in points for value in values.values()))
                self.assertGreater(interval, 0)
                self.assertGreater(rb_interval, 0)
                self.assertGreaterEqual(validate_schedule(points, interval, ramp_start,
                                                          ramp_end, True), .05 - 1e-9)


if __name__ == '__main__':
    unittest.main()
