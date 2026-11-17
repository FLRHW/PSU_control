"""Offline storage forecast regression; no hardware, Qt or real disk dependency."""
import math
import unittest
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch
import cpx400dp_storage as storage

Usage = namedtuple('Usage', 'total used free')


class StorageForecastTests(unittest.TestCase):
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
