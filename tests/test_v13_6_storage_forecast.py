"""Offline storage forecast regression; no hardware, Qt or real disk dependency."""
import math
import unittest
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch
import cpx400dp_storage as storage

Usage = namedtuple('Usage', 'total used free')


class StorageForecastTests(unittest.TestCase):
    def test_live_monitor_warns_only_at_low_space_and_throttles(self):
        clock = [100.]
        disk = [120 * 1024 * 1024]
        calls = []
        monitor = storage.DiskSpaceMonitor(
            "/tmp/experiment.csv", reserve_bytes=256 * 1024 * 1024,
            check_interval_s=30, repeat_interval_s=300,
            monotonic=lambda: clock[0],
            disk_usage=lambda folder: (calls.append(folder) or Usage(0, 0, disk[0])))
        self.assertIn("[STORAGE WARNING]", monitor.check())
        self.assertEqual(len(calls), 1)
        clock[0] += 3
        self.assertIsNone(monitor.check())
        self.assertEqual(len(calls), 1)
        clock[0] += 31
        self.assertIsNone(monitor.check())
        self.assertEqual(len(calls), 2)
        clock[0] += 301
        disk[0] = 800 * 1024 * 1024
        self.assertIsNone(monitor.check())
        self.assertEqual(len(calls), 3)
        clock[0] += 31
        disk[0] = 100 * 1024 * 1024
        self.assertIn("[STORAGE WARNING]", monitor.check())

    def test_live_monitor_probe_failures_do_not_affect_runner(self):
        monitor = storage.DiskSpaceMonitor(
            "/tmp/experiment.csv", disk_usage=lambda _: (_ for _ in ()).throw(OSError("disk")))
        self.assertIsNone(monitor.check())

    def test_runner_live_monitor_only_warns_and_does_not_issue_commands(self):
        source = (Path(__file__).resolve().parents[1] /
                  "scripts" / "cpx400dp_run_enhanced.py").read_text()
        self.assertIn("disk_monitor = DiskSpaceMonitor(log_path)", source)
        heartbeat = source[source.index("def heartbeat(phase, force=False):"):
                           source.index("def wait_until(deadline, phase):")]
        self.assertIn("disk_monitor.check()", heartbeat)
        self.assertIn("print(disk_warning, flush=True)", heartbeat)
        self.assertNotIn("send(sock", heartbeat)
        disk_poll = heartbeat[heartbeat.index("disk_warning = disk_monitor.check()"):
                              heartbeat.index("if start is None or next_progress_at is None")]
        self.assertNotIn("raise", disk_poll)
        self.assertIn("raise RecordingWriteFailure", heartbeat)


    def test_no_warning_with_sufficient_capacity(self):
        result = storage.storage_forecast(
            Path('/tmp/measurements.csv'), 1000, .05, .1, 2,
            disk_usage=lambda _: Usage(20_000_000_000, 0, 20_000_000_000))
        self.assertIsNone(result)

    def test_long_run_low_capacity_warns_but_does_not_block(self):
        output = Path('/tmp/measurements.csv')
        observed = []
        def check(path):
            observed.append(path)
            return Usage(2_000_000_000, 0, 1_000_000_000)
        message = storage.storage_forecast(output, 1000 * 3600, .05, .05, 2,
                                           disk_usage=check)
        self.assertEqual(observed, [output.parent])
        self.assertIn('[STORAGE WARNING]', message)
        self.assertIn('The run is not blocked', message)

    def test_includes_readbacks_even_for_sparse_commands(self):
        few_readbacks = storage.storage_forecast(
            '/tmp/a.csv', 1_000, 5, 10, 2,
            disk_usage=lambda _: Usage(2_000_000_000, 0, 1_000_000_000))
        rapid_readbacks = storage.storage_forecast(
            '/tmp/a.csv', 1_000, 5, .001, 2,
            disk_usage=lambda _: Usage(2_000_000_000, 0, 1_000_000_000))
        self.assertIsNone(few_readbacks)
        self.assertIsNotNone(rapid_readbacks)

    def test_invalid_and_unavailable_disk_probe_fail_open(self):
        def unavailable(_):
            raise OSError('mount inaccessible')
        self.assertIsNone(storage.storage_forecast('/tmp/a.csv', 100, .05, .05, 2,
                                                   disk_usage=unavailable))
        self.assertIsNone(storage.storage_forecast('/tmp/a.csv', math.inf, .05, .05, 2))
        self.assertIsNone(storage.storage_forecast('/tmp/a.csv', 100, 0, .05, 2))

    def test_runner_calls_preflight_before_opening_log_and_psu(self):
        source = (Path(__file__).resolve().parents[1] /
                  'scripts' / 'cpx400dp_run_enhanced.py').read_text()
        start = source.index('def execute(')
        relevant = source[start:source.index('def main():', start)]
        forecast = relevant.index('storage_forecast(')
        log_open = relevant.index("with log_path.open(")
        self.assertLess(forecast, log_open)
        self.assertIn('print(storage_warning, flush=True)', relevant)


if __name__ == '__main__':
    unittest.main()
