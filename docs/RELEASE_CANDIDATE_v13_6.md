# v13.6 release candidate — preparation notes

**Target branch:** dev. **Stable branch:** main at v13.5.
**Decision:** NOT RELEASED; do not create a release tag, push main,
or merge without explicit user approval and real hardware acceptance.

## Changes since v13.5

- Linux direct-Ethernet discovery and read-only Test connection under
  Network settings, verified static-IP/interface remembered across GUI restarts
- Lazy long-duration profile schedule and bounded-gap checking for
  50 ms minimum updates; seconds/minutes/hours/days preview/report axes
- Read-and-clear, last observed CC/CC/UNREG/FAULT *events* displayed
  conservatively (not instantaneous regulation mode)
- Streaming large-log HTML report when CSV is >=8 MiB, with 1200-bin
  extrema overview, per-channel local data chunks, file:// on-demand
  loading, direct elapsed-time-window navigation and cursor comparisons
- Advisory pre-run and runtime storage forecasts, low-space warnings;
  no automatic output changes or log deletion
- Read-only recording audit that separates logged post-interruption
  cleanup from missing evidence and never assumes a safe physical state
- CSV write/flush failure containment. Active-run logging errors
  trigger configured restoration attempts. Failures within cleanup
  cannot suppress final LOCAL. Failed recording exits nonzero and
  automatic report generation is skipped for that failed recording.
- Sparse 24h, 7d, 1000h profiles; 90 s screenshot preview fixture and
  separate low-voltage optional powered bench demonstration profile.

## Current evidence and release gates

| Gate | Evidence needed |
| --- | --- |
| Python unit suite | GitHub Actions dev latest SHA PASS |
| Headless-browser report | Chromium file:// smoke test PASS; synthetic 50ms excursion |
| CSV fault injection | Error during setpoint and final cleanup writes; restoration before LOCAL |
| Static IP / GUI persistence | User already verified both restored fields across relaunch |
| Instrument connectivity | User already verified read-only Test connection on 192.168.71.2 |
| Basic real PSU run | User-supervised 90s low-voltage demo or equivalent |
| Physical restoration | Check actual CH1 original V/I/enable and LOCAL, not CSV alone |
| Screenshots | Optional user-supplied real screenshots for README, not a release blocker |
| CV/CC indication | Optional comparison with PSU front panel; describe as last event |
| Long-run reliability | NOT claimed; multi-hour endurance and crash/power-loss remain pending |

## Safety and known limitations

- PSU is not a safety-interlocked unattended power system. A hard kill,
  full system power loss, a disconnected PSU socket, or failed restoration
  can leave outputs at an unknown state; inspect the actual front panel.
- A successful logged final_state_verified/local_sent pair proves only
  that the application recorded those events, not that terminal voltage
  is independently safe.
- Disk failures in the CSV are now contained in the runner code and
  fault-injected offline, but power-failure recovery and physical
  ENOSPC conditions cannot be certified with software mocks.
- Existing NetworkManager configurations for two dedicated instrument
  links are user-validated and MUST NOT be changed during release.
- The large HTML report needs its matching _report_data directory.
  Preserve raw CSV as source of truth; no background cleanup/deletion.
- Last observed LSR CV/CC events are read-and-clear status history, not
  continuous CV/CC measurements.
- Synthetic screenshots/reports must be clearly labelled synthetic.
- Preserve local untracked profile files, especially profiles/18.csv.

## Release procedure (future; approval required)

1. Complete docs/HARDWARE_ACCEPTANCE_v13_6.md and record dates, logs,
   actual observed PSU state and screenshots if provided.
2. Confirm full offline CI PASS on the final dev commit, including
   browser_report and unittest jobs. Confirm working tree and all docs.
3. Compare main..dev and check changes limited to intended application,
   tests, examples, docs and workflow. Check no personal IP secrets,
   serial numbers in screenshots or user-local reports are committed.
4. Prepare a PR dev -> main for user review, preserving the v13.5 tag
   and existing artifacts. Never force-push main. Update README with
   actual evidence and screenshot links only after files exist.
5. After explicit approval, merge and tag v13.6; record exact merge
   SHA, tag SHA, CI run and hardware validation. Do not declare v13.6
   stable before this approval.

## Next status entry

Record the exact final dev HEAD commit, latest GitHub Actions links and
the final hardware checklist result in docs/SESSION_STATE.md.
Maintain PROJECT_HANDOVER.md and SESSION_STATE.md after any subsequent
source changes.
