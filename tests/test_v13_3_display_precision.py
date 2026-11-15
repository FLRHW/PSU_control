"""Ensure display precision is two decimals without modifying SCPI command precision."""
import ast
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class DisplayPrecisionTests(unittest.TestCase):
    def test_gui_two_decimal_measurements_and_setpoints(self):
        src=(ROOT/'scripts/cpx400dp_gui.py').read_text()
        self.assertIn('spin.setDecimals(2)',src)
        self.assertIn('Programmed: {v:.2f} V / {a:.2f} A',src)
        self.assertIn('Measured: {voltage:.2f} V    {current:.2f} A',src)
        self.assertIn("{values[\"voltage_v\"]:.2f} V",src)
        self.assertIn("{values[\"current_a\"]:.2f} A",src)
        ast.parse(src)
    def test_runner_scpi_retains_original_precision(self):
        src=(ROOT/'scripts/cpx400dp_run_enhanced.py').read_text()
        self.assertIn("{voltage:.3f};I{ch} {limit:.3f}",src)
