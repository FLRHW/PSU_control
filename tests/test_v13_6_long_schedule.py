"""v13.6 first-increment checks for long-duration scheduling (offline only)."""
import itertools
import time
import unittest

import cpx400dp_run_enhanced as runner


class LongScheduleTests(unittest.TestCase):
    def test_short_schedule_preserves_unique_rounded_ticks(self):
        actual = list(runner.schedule_for(0.20, 0.05, [0, 0.10, 0.15]))
        self.assertEqual(actual, [0.0, 0.05, 0.10, 0.15, 0.20])

    def test_irregular_keyframe_is_sorted_and_deduplicated(self):
        self.assertEqual(
            list(runner.schedule_for(0.3, 0.1, [0.2, 0.0, 0.2])),
            [0.0, 0.1, 0.2, 0.3])

    def test_1000h_50ms_schedule_is_lazy_and_validates_quickly(self):
        duration = 1000 * 3600
        points = [(0., {1:(1,1,None)}),
                  (1800000., {1:(2,1,None)}),
                  (float(duration), {1:(3,1,None)})]
        start = time.monotonic()
        self.assertAlmostEqual(
            runner.validate_schedule(points, 0.05, 0, 0, True),
            0.05, places=7)
        self.assertLess(time.monotonic() - start, 3.0)
        schedule = runner.schedule_for(duration, 0.05, (t for t, _ in points))
        self.assertEqual(list(itertools.islice(schedule, 4)),
                         [0.0, 0.05, 0.10, 0.15])

    def test_1000h_near_regular_keyframe_rejected(self):
        points = [(0., {1:(1,1,None)}),
                  (1800000.025, {1:(2,1,None)}),
                  (3600000., {1:(3,1,None)})]
        with self.assertRaisesRegex(ValueError, 'Unsafe scheduled setpoint spacing'):
            runner.validate_schedule(points, 0.05, 0, 0, True)

    def test_end_phase_short_gap_rejected_without_large_schedule(self):
        points = [(0., {1:(1,1,None)}),
                  (3600000.02, {1:(1,1,None)})]
        with self.assertRaisesRegex(ValueError, 'Unsafe scheduled setpoint spacing'):
            runner.validate_schedule(points, 0.05, 0, 0, True)

    def test_ramp_short_gap_still_rejected(self):
        points = [(0., {1:(1,1,None)}), (10., {1:(2,1,None)})]
        with self.assertRaisesRegex(ValueError, 'initial ramp'):
            runner.validate_schedule(points, 0.05, 0.12, 0, True)


if __name__ == '__main__':
    unittest.main()
