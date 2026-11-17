"""Offline tests for large-log reports: bounded memory, extrema, and file layout."""
import csv
import json
import re
import shutil
import subprocess
import tempfile
import tracemalloc
import unittest
from pathlib import Path

from cpx400dp_report import generate
import cpx400dp_report_stream as streaming

FIELDS = ["utc_time", "elapsed_s", "event", "scheduled_s", "channel",
          "set_voltage_v", "current_limit_a", "requested_enable",
          "measured_voltage_v", "measured_current_a", "lateness_ms",
          "readback_duration_ms", "note"]


def create_log(path, count):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(dict(utc_time="2026-11-17T20:00:00+00:00", event="config",
                             note="mode=step"))
        for i in range(count):
            ch = 1 + (i % 2)
            t = i * .05
            if i % 2:
                writer.writerow(dict(event="readback", channel=ch,
                                     elapsed_s=t, measured_voltage_v="5.0" if i != 301 else "39.0",
                                     measured_current_a="1.0"))
            else:
                writer.writerow(dict(event="setpoint", channel=ch,
                                     elapsed_s=t, set_voltage_v="5.0",
                                     current_limit_a="1.0", lateness_ms="0.4"))
        for ch in (1, 2):
            writer.writerow(dict(event="final_state_verified", channel=ch,
                                 elapsed_s=count * .05))
        writer.writerow(dict(event="local_sent", elapsed_s=count * .05))


class StreamingReportTests(unittest.TestCase):
    def test_small_default_report_remains_single_html(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "short_measurements.csv"
            create_log(csv_path, 24)
            out = generate(csv_path)
            self.assertTrue(out.is_file())
            self.assertIn("CPX400DP experiment report", out.read_text())
            self.assertFalse(out.with_name(out.stem + "_data").exists())

    def test_stream_chunks_and_finite_summary_overview(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path = Path(d) / "large_measurements.csv"
            create_log(csv_path, 9000)
            out = generate(csv_path, force_stream=True)
            doc = out.read_text(encoding="utf-8")
            self.assertIn("local detail chunks", doc)
            self.assertIn("Cursors: OFF", doc)
            self.assertIn('class="jump-time"', doc)
            self.assertIn('class="jump-span"', doc)
            self.assertIn("Full resolution: loaded local detail chunks.", doc)
            self.assertIn("COMPLETED", doc)
            self.assertIn("LOCAL command", doc)
            self.assertIn("39.00 W", doc)
            self.assertNotIn("https://", doc)
            self.assertNotIn("http://", doc.replace("http://www.w3.org/2000/svg", ""))
            folder = out.with_name(out.stem + "_data")
            chunks = sorted(folder.glob("*.js"))
            self.assertGreaterEqual(len(chunks), 3)
            self.assertLessEqual(len(chunks), 4)
            self.assertTrue(any("39.0" in item.read_text() for item in chunks))
            self.assertIn('"p":[', doc)
            self.assertIn("39.0", doc)  # overview extrema preserve isolated peak
            self.assertIn(folder.name + "/c2_", doc)

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable for JS syntax check")
    def test_generated_viewer_javascript_parses(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "viewer_measurements.csv"
            create_log(path, 9000)
            html_file = generate(path, force_stream=True)
            page = html_file.read_text(encoding="utf-8")
            scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", page, re.DOTALL)
            self.assertEqual(len(scripts), 2)
            script_path = Path(d) / "viewer.js"
            script_path.write_text(scripts[-1], encoding="utf-8")
            subprocess.run(["node", "--check", str(script_path)], check=True,
                           capture_output=True, text=True)

    def test_empty_and_missing_channel_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "empty.csv"
            p.write_text(",".join(FIELDS) + "\n")
            with self.assertRaisesRegex(ValueError, "no events"):
                generate(p, force_stream=True)
            p.write_text(",".join(FIELDS) + "\n" +
                         "2026-11-17T00:00:00,0,config,,,,,,,,,,\n")
            with self.assertRaisesRegex(ValueError, "no channel data"):
                generate(p, force_stream=True)

    def test_streaming_heap_is_sublinear_to_csv_rows(self):
        with tempfile.TemporaryDirectory() as d:
            small = Path(d) / "sample_measurements.csv"
            create_log(small, 32000)
            tracemalloc.start()
            try:
                generate(small, force_stream=True)
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            # A whole-row parse with multiple copies typically costs >30 MiB.
            # Allow memory for bounded bins, chunk buffers and HTML template.
            self.assertLess(peak, 28 * 1024 * 1024, f"peak was {peak} bytes")

    def test_automatic_switch_and_forced_option_are_present(self):
        source = (Path(__file__).resolve().parents[1] /
                  "scripts" / "cpx400dp_report.py").read_text()
        self.assertIn("8 * 1024 * 1024", source)
        self.assertIn("generate_stream(log_file", source)
        self.assertIn("'--stream'", source)
        self.assertEqual(streaming.MAX_CHUNK_ROWS, 4096)


if __name__ == "__main__":
    unittest.main()
