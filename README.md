# CPX400DP PSU Control

Linux/Kubuntu desktop tool for controlling a dual-channel
Aim-TTi / Thurlby Thandar CPX400DP power supply over Ethernet:
CSV profile playback, standalone and paused-profile manual control,
offline preview, measured readbacks, and interactive HTML reports.

**Release status:** v13.6 is a release candidate on `dev`;
**v13.5 on `main` remains stable**. On 22 November 2026,
a real supervised 90-second hardware demonstration completed
with zero readback errors and GUI restoration verified;
the user also confirmed LOCAL returned on the actual PSU.
Original CH1 programmed V/I/output-enable front-panel values
have not been independently reported. v13.6 will not be
merged/tagged without remaining release acceptance and
explicit user approval.

## Features

- Two-channel CSV profiles with step or linear interpolation,
  output enable control, optional initial/final ramps and saved-state
  restoration; minimum scheduled setpoint spacing 50 ms
- Pausing a run, temporarily changing settings with Manual Control,
  and guarded Resume; Stop requests verified restoration and LOCAL
- Standalone Manual Control with programmed V/I/enable state,
  measurement readbacks and clear output-state indicators
- Read-only PSU discovery/identification in **Network settings…**,
  with last successfully verified host/interface remembered
- Offline previews and dynamic seconds/minutes/hours/days axes;
  lazy scheduling of very long sparse-keyframe profiles
- Offline HTML measurement reports with selectable V/I/P traces,
  zoom, pan, cursors and large-log local on-demand detail chunks
- Read-only recording audit and advisory disk-space warnings,
  plus CSV write-failure containment to preserve cleanup attempts

For complete behaviour, limitations and historical findings see
[engineering handover](docs/PROJECT_HANDOVER.md),
[current session state](docs/SESSION_STATE.md), and the
[v13.6 release candidate](docs/RELEASE_CANDIDATE_v13_6.md).

## Installation and launch

The application uses Python 3 on Linux and the Qt GUI binding already
available on the workstation (PyQt5 or PySide6). Offline preview
and report plots require Matplotlib. No internet is needed at runtime.

Launch on Kubuntu from the project root:

```bash
/usr/bin/python3 scripts/cpx400dp_gui.py
```

In the GUI, choose a CSV profile, select a folder for generated reports
(e.g. `reports/`), preview it, and open **Network settings…** to
enter the instrument IPv4 address/interface if needed. **Test connection**
performs read-only `*IDN?` identification and closes its test socket.
Only pressing Start or connecting Manual Control establishes a
control session. The runner takes a verified initial snapshot before
changing programmed settings, attempts configured final restoration,
and sends `LOCAL` as its last instrument command.

On the validated dual-instrument bench the PSU uses
`192.168.71.2` over the dedicated Dell D6000 Ethernet adapter.
Another workstation will have different addresses and interface names;
do not copy or overwrite other networking configurations. The earlier
link-local discovery and opt-in adapter setup remain available but are
not necessary for the already-configured static bench link.

## Example CSV profiles

| File | Duration | Purpose |
| --- | --- | --- |
| [Release GUI screenshot preview](profiles/examples/release_demo_90s_preview.csv) | 90 s | Two-channel step plot; both outputs commanded OFF; offline screenshot fixture |
| [24-hour step preview](profiles/examples/long_24h_step_preview.csv) | 24 h | Five sparse keyframes; output OFF |
| [Seven-day linear preview](profiles/examples/long_7d_linear_preview.csv) | 7 days | Eight dual-channel keyframes; outputs OFF |
| [1,000-hour step preview](profiles/examples/long_1000h_sparse_preview.csv) | 1,000 h | Eleven dual-channel keyframes; outputs OFF |
| [Optional supervised live demo](profiles/examples/hardware_demo_90s_REQUIRES_LOAD.csv) | 90 s | CH1 up to 3 V with a 0.10 A current limit; **REQUIRES an appropriate resistive load** |

All preview fixtures are for inspecting time axes and waveforms
**without running the PSU**. Their requested OFF state is not permission
for unattended hardware operation. The live demo needs a bench safety
check and must be supervised. See
[the short hardware acceptance checklist](docs/HARDWARE_ACCEPTANCE_v13_6.md).

Generate a 1,000-hour offline preview:

```bash
/usr/bin/python3 scripts/cpx400dp_run_enhanced.py \
  --preview profiles/examples/long_1000h_sparse_preview.csv
```

A synthetic 1,000-hour measurement CSV with a brief artificial peak
is available in the supplementary examples bundle supplied during
development; it is **fictional**, never a real PSU hardware run.

## Reports and recording checks

For CSV logs smaller than 8 MiB, the report is a self-contained HTML
file. Larger logs generate an HTML report **plus a matching
`*_report_data/` directory**, containing per-channel data chunks
loaded as the browser zooms in. Keep the folder beside its report HTML;
preserve the original measurement CSV as the authoritative source.

To generate a report from a recording:

```bash
/usr/bin/python3 scripts/cpx400dp_report.py reports/example_measurements.csv
```

The report generator needs no connection to the PSU. For an audit
of existing logs (including interrupted runs):

```bash
/usr/bin/python3 scripts/cpx400dp_recording_audit.py reports
```

Audits classify the **recorded** final-state and LOCAL events, not
actual electrical output or front-panel LOCAL confirmation.

To archive an experiment **after it has finished**, without deleting
anything or omitting large-report sidecars:

```bash
/usr/bin/python3 scripts/cpx400dp_archive.py reports/example_measurements.csv
```

The archive includes a checksum manifest, refuses to overwrite an
existing ZIP and retains the original files. It is opt-in only.
Consult [storage and recovery limitations](docs/RECORDING_RECOVERY.md)
and [large-report details](docs/REPORT_STREAMING.md).

## Offline regression

```bash
PYTHONPATH=scripts /usr/bin/python3 -m unittest discover -s tests -p 'test_*.py'
```

GitHub Actions additionally runs the full Python suite and an isolated
headless Chromium browser test for a synthetic long report. Browser
testing is performed in CI; the user does not need to install
Playwright locally.

## Release screenshots

Seven **real hardware/UI screenshots** from 22 November 2026
were supplied and reviewed, showing the 90-second preview,
1,000-hour offline preview, paused Manual Control, completed
run, HTML charts and diagnostic summary. A privacy-cropped
PNG bundle has been prepared, but the files **have not yet been
committed to GitHub**. README galleries will be linked once
the actual PNG assets exist under `docs/screenshots/`.
See [hardware acceptance details](docs/HARDWARE_ACCEPTANCE_v13_6.md).

The screenshot preview used GUI application defaults in
**linear mode** even though example CSV metadata requests
step mode. The paused-profile screenshot also shows a
manual current limit of 1.00 A rather than the original
example's 0.10 A. Neither should be misrepresented in
captions.

## Version history and development records

| Version | Status |
| --- | --- |
| v13.3 | [Historical release notes](docs/RELEASE_v13_3.md) |
| v13.4 | [Historical release notes](docs/RELEASE_v13_4.md) |
| v13.5 | Stable `main`; hardware stages 1–3 passed, see [historical release](docs/RELEASE_v13_5.md) |
| v13.6 | Candidate on `dev`; see [release gates](docs/RELEASE_CANDIDATE_v13_6.md) and [backlog](docs/BACKLOG.md) |

The development process maintains two documents:
`docs/PROJECT_HANDOVER.md` for durable design/safety knowledge and
`docs/SESSION_STATE.md` for actual changes, validation evidence and next steps.

**Safety:** this is laboratory automation, not a hardware interlock.
A sudden PC power loss, network disconnection, full disk or PSU fault
can leave outputs in an unknown state. Never infer safe terminal
conditions solely from CSV log events, and always inspect the real
instrument after an unexpected interruption. Do not run extended
experiments unattended without a separately engineered safety plan.
