# Long-duration offline preview examples

These examples are intentionally sparse (5, 8 and 11 CSV keyframes) yet
cover 24 hours, 7 days and 1,000 hours. They are **preview fixtures**,
not recommended unattended hardware runs.

| Profile | Duration | Channels | Mode | Interval | Keyframes |
|---|---:|---|---|---:|---:|
| long_24h_step_preview.csv | 24 h | 1 | step | 10 s | 5 |
| long_7d_linear_preview.csv | 7 days | 1,2 | linear | 60 s | 8 |
| long_1000h_sparse_preview.csv | 1000 h | 1,2 | step | 60 s | 11 |

All records command outputs OFF, set a low 0.05 A current limit and
request restoration of prior channel states. This reduces risk for
experimentation but does NOT authorize unattended hardware operation.
Preview the files without starting a profile. The PSU address in the
metadata uses the dedicated bench static IP 192.168.71.2; the GUI may
override it with its last verified destination.

To preview an example without touching the PSU:

    /usr/bin/python3 scripts/cpx400dp_run_enhanced.py --preview profiles/examples/long_1000h_sparse_preview.csv

The GUI also supports selecting the CSV and generating its offline preview.

A separate downloadable example bundle shared in ChatGPT includes
synthetic_1000h_measurements.csv, a fictional 1000-hour recording with
approximately 120,000 readbacks and a deliberately inserted 50 ms
transient near elapsed second 3,599,950.05. That CSV is for exercising
the new HTML report viewer only. Its final-state and LOCAL event markers
are fictitious and do not document a real instrument result. It is not
committed to the repository due to its size.

Generate a report from it using:

    /usr/bin/python3 scripts/cpx400dp_report.py /path/to/synthetic_1000h_measurements.csv

The HTML file and its matching _report_data directory must stay
together. Use Jump to elapsed second 3599950.05 and Window 1 (s)
to examine the synthetic excursion.
