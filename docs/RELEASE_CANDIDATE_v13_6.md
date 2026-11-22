# v13.6 release candidate — preparation notes

## Post-fix GUI acceptance — 22 November 2026, 17:56 UTC

Eight user-supplied real screenshots of the 15-ohm experiment
visually confirm the magenta NOW marker moves through the
step-profile preview, and the runner's conservative
V/I-derived regulation indicator reports `CV likely`
(3.99 V / 0.27 A) and `CC likely` (2.26 V / 0.15 A)
at appropriate phases. Thus the previous persistent UNKNOWN
bug is **hardware visually validated as resolved**.
No separate PSU CV/CC status query was added.

The completion screenshot and final HTML report summary record
COMPLETED, 495 successful readbacks, 0 failed, 2.073 ms
max logged setpoint lateness, 0 output-health warnings,
0 unexplained high readbacks, 3 expected-settling readbacks,
health OK, physical output MATCHED, CH1 programmed final
state VERIFIED and LOCAL command SENT. The chart shows
8.06 W peak, 2.10 W mean, 259.4 J energy estimate.
An optional paused Manual Control screenshot records
CH1 10.00 V / 2.00 A programmed, measured 9.99 V /
0.67 A, demonstrating temporary manual overrides; do
not conflate this with the demo CSV's programmed maxima.

The current-turn screenshots are NOT uploaded as
`docs/screenshots` binary files in GitHub. Report HTML/CSV
for this latest 17:56 run has not been independently parsed
from a new uploaded file in this turn; reported figures
are transcribed from user screenshots. Prior direct
physical LOCAL confirmation was from an earlier run.
No release/merge/tag authorised; main remains v13.5.


## Hardware and screenshot evidence — 22 November 2026

The user completed the supervised 90-second CH1 demonstration,
and supplied seven real GUI/browser screenshots. Evidence:
Profile Runner "Completed — restoration verified", process exit 0;
HTML run summary COMPLETED with 558 successful readbacks,
0 failed readbacks, 0 output-health warnings, 0 implausible
high readbacks, peak logged setpoint lateness 0.877 ms;
CH1 programmed final state VERIFIED; LOCAL command SENT.
User separately stated **LOCAL restored** on the actual PSU.
Pauses/resumes and temporary manual control are visible.

The user has not separately reported observing all three final
CH1 programmed V/I/output-enable settings at the physical
front panel. Treat the GUI verification as software evidence,
not a substitute. The 90s session is hardware-validated,
but this does not demonstrate disk exhaustion recovery,
PC power-loss safety or multi-hour/1000h unattended endurance.

During a pause, the UI shows CH1 programmed 3.00 V / 1.00 A,
measured 2.99 V / 0.20 A, output ON: manual settings differed
from the example profile's baseline 0.10 A current limit.
Preview images display the GUI's effective persistent
Mode=linear despite step-mode CSV metadata; this is documented
application override behaviour. Do not mislabel those
screenshots as proof of the CSV's unmodified step mode.

Privacy-cropped screenshots and captions are prepared in
an external bundle for the user. **No actual screenshot PNGs
have yet been committed to the GitHub repository**, so README
image paths must remain unlinked until uploaded. Release must
remain on dev pending the physical V/I/output-enable
confirmation, screenshot publication (if desired), final CI
check and explicit approval to merge/tag.


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
