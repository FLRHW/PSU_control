# v13.6 release candidate — minimal hardware acceptance

**Status:** preparation checklist, not evidence of acceptance. Run after the
latest dev CI passes. Do not merge dev into main without explicit approval.

## Already covered offline; do not spend bench time on these

- All Python unit tests, mocked single-socket ownership and restore/LOCAL order
- Injected measurement CSV ENOSPC failures during active run, restoration
  logging and post-LOCAL summary; error status and mandatory cleanup attempts
- Generated 1000-hour synthetic HTML report in headless Chromium using file://,
  local detail chunks, 50 ms excursion, time navigation and cursors
- Sparse 24h, 7d, 1000h profile validation; 90-second release-demo profile
- Read-only disk monitor, recovery log audit and static-IP field persistence
- No real 1000-hour PSU run, physical full-disk experiment or power-cycle test
  is required for this candidate

## Five-minute supervised bench acceptance — one small run

**Safety setup:** connect CH1 to a simple resistive load approximately
47 ohms rated at least 1 W, if available. At 3 V, this draws about
64 mA and dissipates less than 0.2 W. No sensitive electronics on the
output. Confirm actual resistor value/rating and wiring before enabling
output. Keep CH2 disconnected/OFF. The proposed demo has a CH1
current limit of 0.10 A and a peak voltage of 3 V. If that test setup
is unavailable, skip the powered demo and report it untested.
This app is not a safety interlock.

1. In the PSU front panel, note the programmed CH1 voltage/current
   and output enable state; for simplest restoration evidence,
   set CH1 to 0.00 V, 0.10 A, output OFF; ensure CH2 OFF.
   Do not leave the bench unattended.
2. In the project directory: git status --short; git pull --ff-only
   origin dev. Do not delete local untracked profiles/18.csv.
3. Launch /usr/bin/python3 scripts/cpx400dp_gui.py. The previously
   verified PSU destination should still be 192.168.71.2 via
   enx0c3796303396. If it is not, use Network settings ->
   Test connection. Do not change host NetworkManager profiles.
4. Select profiles/examples/hardware_demo_90s_REQUIRES_LOAD.csv.
   Set report output directory to reports/; preview first and
   check the voltage limit, output-enable transitions and schedule.
5. Start the supervised run. Optionally Pause around 30 s,
   enter paused-profile Manual Control, set CH1 to 1.50 V with
   0.10 A limit and output ON, then Resume. This exercises the
   previously proven pause/manual/resume path within the same run.
   Pause freezes profile time, so this need not be timed precisely.
   If anything behaves unexpectedly, use Stop/safe cleanup;
   independently check the instrument.
6. Let the 90 s profile finish, verify on the real front panel
   that CH1 returned to the recorded original settings and
   output enable and that control returned to LOCAL (front-panel
   LOCK may require cancelling separately). Inspect the generated
   console/report: both a final_state_verified event and
   local_sent are expected for CH1; readback errors should be zero.
   Never treat log events as independent physical confirmation.
7. Run the audit against the exact generated *_measurements*.csv:
   /usr/bin/python3 scripts/cpx400dp_recording_audit.py reports
   (or specify the exact CSV for less output).

This single run is the mandatory new physical test. An additional
short Stop-restoration test is reasonable if the one-run result
shows anomalies, but previous v13.5 Stop tests already passed.

## Screenshot capture — prepare README evidence in one pass

Use the operating system screenshot tool; capture only real
application/browser windows, not account details or private data.
Prefer 1280-1600 px wide screenshots, readable text, and no
cropped controls. Save PNG files locally, then commit only with
the user's review/approval. Suggested paths under docs/screenshots/:

- 01-profile-preview.png: GUI with release_demo_90s_preview.csv
  selected and preview plot, WITHOUT running hardware.
- 02-long-duration-preview.png: 1000h sparse preview time axis.
- 03-network-settings.png: verified static IP/interface, optionally
  redact PSU serial; use already hardware-validated connection.
- 04-run-progress.png: live 90 s demo while safely connected to load.
- 05-paused-manual.png: optional paused-profile manual tab and clear
  output state, captured during the same run.
- 06-experiment-report.png: HTML report of completed 90 s run.
- 07-synthetic-1000h-detail.png: synthetic file:// report zoomed
  to elapsed time 3599950.05, window 1 s. Clearly label SYNTHETIC.

The GitHub CI browser job also uploads a short-lived synthetic screenshot
artifact; it is not a substitute for live-run photos. Do not add image
references to main README until their actual files are committed.

## Additional optional checks (only if convenient)

- Verify Manual Control's CV/CC label changes against front panel using
  suitable **separately prepared** resistive loads. LSR is an event register,
  so this is NOT a continuous regulation-mode reading. Keep output
  disabled while changing loads and respect resistor power limits.
- An operator-supervised multi-hour run is the gate for making
  multi-hour robustness claims; until then avoid any unattended
  multi-day reliability claim.
- No deliberate PSU test on a full disk or sudden host power loss:
  those are best handled with fault-injection/offline evidence and a
  later controlled risk assessment.

## Reporting back

One short message is enough: "90s test passed/failed; CH1 restored
V/A/enable; LOCAL sent; readback errors count; screenshots captured
yes/no" plus the relevant console excerpt only if anything failed.
Do not send thousands of CSV rows unless a failure needs investigation.
