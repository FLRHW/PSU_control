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

## Optional 15-ohm, 10-W continuous resistor experiment

`hardware_demo_90s_15ohm_REQUIRES_LOAD.csv` is an additional
90-second **supervised CH1** experiment designed for a 15-ohm,
10-W continuously rated resistor. Peak programmed 8.0 V
corresponds to approximately **0.53 A and 4.27 W** at 15 ohms
(allowing for resistor tolerances). Current limit is at most
0.65 A in the file. Between 40 and 50 seconds, commanded
voltage remains 6 V while current limit becomes 0.15 A;
if the resistor remains about 15 ohms, the supply will
likely enter current limiting and settle around 2.25 V
and 0.15 A. The current limit returns to 0.65 A at
50 seconds, permitting a return to CV mode.
This demonstrates that measured output is not necessarily
identical to the programmed voltage during CC limiting.

**Important:** GUI application defaults for mode/intervals/
initial ramp/final ramp override CSV metadata. Inspect them
and the saved initial CH1 voltage/current/output-enable
state before running. A previously programmed voltage
can appear in the initial ramp even when output was
initially OFF. For an uncomplicated controlled test,
start with CH1 output OFF, programmed 0 V and a sensible
current limit, select **step** mode and initial/final ramps
appropriate to the setup. Do not operate unattended.
This file does not guarantee thermal safety for another
resistance, another device, inadequate ventilation or
unexpected restoration settings.

The Profile Runner adds a magenta GUI-only `NOW` marker
to its preview. It is an *estimated* profile-time position,
not a precise representation of SCPI command latency;
it freezes during Pause. Channel cards show `CV likely`
or `CC likely` from existing programmed V/I and logged
measured V/I, otherwise `UNKNOWN`. These are estimates,
**not measured continuous regulation modes or LSR register
events**; no additional PSU commands are issued for them.

