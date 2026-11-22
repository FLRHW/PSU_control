# CPX400DP — current session state

## 2026-11-22 — Runner CV/CC label flicker: cause and minimal fix

After new 15-ohm supervised test the user reported Profile Runner
regulation label was UNKNOWN for virtually the whole run, and
preferred removing it if unreliable. Uploaded screenshots include
a PAUSED frame at ~26% showing CV likely, demonstrating the
calculation can work briefly. Inspection of the source revealed
a deterministic UI bug: CSV `setpoint` rows appear every 50ms,
but `readback` rows only every 250ms. The GUI called
`update_runner_regulation(ch)` with no measured values on
**every** non-readback setpoint; the estimator therefore
reset to UNKNOWN 50ms after almost every successful readback.
The user saw an almost permanent UNKNOWN indicator even in
valid CV operation. Fix on dev: defer regulation UI updates
on setpoint changes until the next measured readback; update
immediately to UNKNOWN on a commanded explicit output OFF,
and continue clearing on run finish. This preserves conservative
measurement-only semantics with no additional PSU communications.

New `test_csv_setpoint_heartbeat_does_not_flicker_mode_to_unknown`
executes the real GUI CSV poll method on a generated sample
measurement log with ON + 4V/0.65A setpoint, 3.98V/0.27A
readback (CV likely), five subsequent 50ms HOLD/setpoints
(no label reset), next 6V/0.15A setpoint plus 2.25V/0.15A
readback (CC likely), and explicit OFF (UNKNOWN). Confirm full
GitHub CI before marking offline-passed.

Real 15-ohm run HTML uploaded
`hardware_demo_90s_15ohm_report_20261122_152131_904777.html`:
COMPLETED; 578 successful readbacks, 0 failed;
0.949ms max logged setpoint lateness; LOCAL sent;
CH1 programmed final state VERIFIED and sampled
physical output MATCHED; 1 unexplained high readback
and 1 expected-settling readback; experiment health
WARNING. Peak sampled power 8.09W, average 1.41W,
estimated energy 203.3J. Readable embedded plot-data
identifies that peak at t=0.02197s with 10.982V and
0.737A, during the initial ramp from user's previous
11V state (NOT the designed 8V plateau). At 15 ohms,
this is about 8.0W, below resistor's rated 10W continuous,
but demonstrates *preexisting PSU settings* are relevant
to power budget. Do not claim entirely warning-free run;
do not infer a physical LOCAL observation from the
HTML 'LOCAL SENT' marker; prior separate user physical
LOCAL validation remains valid only for earlier run.

No new hardware run is strictly required to validate
the bug fix if UI evidence is otherwise sufficient;
if desired, one brief supervised exercise can confirm
the indicator remains stable, respecting previous PSU
starting output state. If further unreliable readings
are reported, prefer hiding/removing the runner label
rather than displaying misleading UNKNOWN continuously.


## 2026-11-22 — New runner GUI features offline CI PASS

Full GitHub Actions workflow **45037162075** succeeded on
`dev` commit `e4db1adae8e1f1deb2eeb0e0fc89b789fe73b760`,
with BOTH the Python offline suite and actual headless
Chromium report job passing. Python regressions include
conservative CV/CC inference, 15-ohm demo profile-power
budget, static GUI marker lifecycle and an offscreen Qt
render test that paints a magenta vertical position marker
over a real QPixmap without modifying its underlying
pixels. Initial CI failures were test infrastructure:
legacy isolated-GUI mocks missing new display methods
(corrected), then a headless Ubuntu runner missing
libEGL.so.1 (installed minimal runtime libraries
in the CI workflow). Final source CI is green.

Latest step-mode hardware screenshot package exported as
`CPX400DP_v13_6_step_mode_screenshots.zip` containing
6 original uploads under `docs/screenshots/`, numbered
08–13, and README.txt; it is provided to the user
for their own GitHub commit. Actual images are NOT yet
in the GitHub repository and no Markdown links to them
should be invented. Existing earlier screenshots are
a separate optional bundle.

Hardware gate for these NEW features remains: briefly
observe magenta NOW marker advances and freezes during
Pause; for the 15-ohm demo, confirm conservative CV/CC
estimate reacts plausibly to the 0.15 A stage and
returns to CV when current limit restored. No new
instrument output-control code was modified. Physical
original programmed-state restoration and LOCAL must
still be verified before release. Historical 90s run
and user-confirmed LOCAL precede this new GUI revision.

`main` stays the v13.5 stable branch, no merge/tag.


## 2026-11-22 — v13.6 follow-up: runner position marker, CV/CC estimates, 15-ohm demo

User submitted **new step-mode/initial-ramp screenshots** from
another supervised 90s run and an actual HTML report. The supplied
HTML summary states: COMPLETED; **469 successful readbacks**,
**0 failed**, max logged setpoint lateness **2.143 ms**,
0 output-health warnings, 0 unexplained high readbacks,
0 expected-settling readbacks, experiment health OK, final
CH1 programmed state VERIFIED and LOCAL command SENT.
Measured sampled power peaked **1.07 W** with
**0.18 W** average and estimated energy **21.7 J**.
Unlike the earlier linear screenshots, updated preview
shows true stepped setpoints and **2 s initial/final
ramp overrides**. Report includes actual pause/resume,
a transient 1 A manual current limit, and diagnostic
LSR1 final=3; simultaneous CV/CC event bits do **not**
establish current mode or event ordering. User's load
is **15 ohms, 10 W continuous, 40 W for 0.5 s**.

User requested (1) a moving vertical 'NOW' line on
the Profile Runner preview and (2) runner CV/CC mode
indication, absent from normal Profile Runner but
historically present as LSR last-event in Manual Control.
Implemented GUI-only marker as a QPainter overlay
in `ProfileProgressImage`, mapping chart time
to the Matplotlib axes x=[0.105,0.88] and updating
every 200 ms based on existing [PROGRESS] heartbeat
and monotonic extrapolation. Subtract initial ramp
duration so marker starts at CSV time 0, freezes during
paused/stopping phases, clamps to plot duration and
stays displayed at 100% after completed run.
No edits to preview PNG/CSV source and no PSU queries.

Added `scripts/cpx400dp_regulation_estimate.py`
and Profile Runner labels `CV likely (V/I estimate)`,
`CC likely (V/I estimate)` or UNKNOWN. Based on
already logged commanded V/current/enable and
measured V/I; rejects OFF, low targets, ambiguous
or implausible values. These are explicitly
**heuristic V/I estimates and NOT instrument-verified
real-time modes**, and separate from the existing
Manual Control last-seen LSR read-and-clear events.
Does not issue extra SCPI LSR reads or alter timing,
socket ownership, PSU safety/restore code. Labels
reset to UNKNOWN after runner exit.

Added `profiles/examples/hardware_demo_90s_15ohm_REQUIRES_LOAD.csv`.
At 15 ohms, maximum 8 V corresponds to ~0.533 A
and **4.27 W**, below resistor's 10 W nominal
continuous rating. Deliberate 6 V/0.15 A interval
at 40-50s should enter CC around 2.25 V if the
resistive load is as stated; a 0.65 A limit at
50s allows return toward CV. Elsewhere maximum
configured I limit is 0.65 A. Live output and
restoration require supervision and careful check
of GUI's persisted initial/final ramps and prior
instrument state. Existing demo profile retained
unchanged as historical evidence, not overwritten.
Added pure inference tests, profile power-budget
checks and headless Qt overlay rendering regression.

**Status:** source implemented; complete CI must be
recorded for the final dev SHA before offline pass
can be claimed. New GUI behaviour has not yet
been physically validated. Earlier 90s hardware
runs predate these new UI additions; they are
not evidence that the moving line/estimation work.
Main stays v13.5, unmerged/untagged. Keep user's
local profiles/18.csv untouched.


## 2026-11-22 — Real 90-second demo completed; LOCAL physically restored

User supplied seven live screenshot captures from v13.6
testing and explicitly confirmed **LOCAL restored on PSU**.
Evidence in actual GUI/report screenshots:
- `release_demo_90s_preview.csv` OFF-output dual-channel
  preview and `long_1000h_sparse_preview.csv` 1000h
  OFF-output offline preview (no hardware implied).
- Real paused-profile Manual Control with CH1 measured
  2.99 V / 0.20 A and output ON; programmed 3.00 V /
  1.00 A. This is temporary manual control, higher
  current limit than the example CSV baseline 0.10 A.
- Completed `hardware_demo_90s_REQUIRES_LOAD.csv`,
  GUI "Completed — restoration verified", runner exit
  code 0, final CH1 display -0.01 V / 0.00 A.
- Actual HTML report: COMPLETED; 558 good readbacks,
  zero failed; 0.877 ms max recorded setpoint lateness;
  0 output-health warnings, 0 unexplained high
  readbacks, 0 expected-settling readbacks;
  CH1 programmed final state VERIFIED; LOCAL command
  SENT. Physical output check N/A (output OFF or
  near-zero intended); this does not independently
  verify terminal electrical safety.
- Real waveform/report zoom with multiple pause/resume
  markers, and real diagnostics snapshot displayed.
  User independently confirmed LOCAL restored.

**Hardware acceptance state:** successful supervised
90s experiment with pause/manual/resume, software
restoration and physically confirmed LOCAL. Actual
front-panel programmed CH1 original V/I/enable values
after completion are not separately reported; do not
claim that check independently completed.

**Documentation/screenshots:** seven original supplied
PNGs privately held in conversation and a cropped,
browser-bookmarks/paths-redacted `CPX400DP_v13_6_readme_screenshots.zip`
prepared for user download and minimal local commit.
They are not currently uploaded to GitHub. Do not
invent GitHub image paths/links before user commits.
Actual screenshots are *not synthetic*.
The preview screenshots show GUI application defaults
Mode=linear, interval=0.05s, readback=0.25s, final
ramp=2s; persisted GUI defaults take precedence over
metadata embedded in the step-mode examples. Explain
this in captions; don't call screenshot a step-mode test.

**Remaining release gate:** seek one concise user
confirmation of physical CH1 original programmed V/I
and output-enable restoration, if it was observed,
and upload supplied screenshots. Then final CI and
explicit release merge approval. No main branch change
or tag has been made. No additional 90s run required
if the user already observed proper programmed state.
No multi-day endurance, real ENOSPC or power-failure
safety claim is supported.


## 2026-11-22 — Stage A final offline acceptance PASS (release-candidate source)

**GitHub Actions run 45033881762: SUCCESS**, on exact `dev`
commit `063b23563ed123d2a45b775c500d3f3955af319e`.
Both independent jobs finished successfully: **Python offline
suite** (including active/cleanup/post-LOCAL simulated CSV
write failures, verified ZIP archiving with missing-sidecar
rejection, long preview profiles, existing socket/restoration
regressions) and **headless Chromium large-report browser**
(file:// local chunk load, synthetic 1000h/50ms peak and cursor).
The browser job saved a 5-day retention screenshot artifact;
its content is SYNTHETIC and not PSU hardware evidence.
Earlier transient CI failures were fixed (browser test SVG
API and legacy assertion scope). Superseded/stranded older
workflow runs were isolated by versioning the CI concurrency
group; final source SHA is fully tested.

**Remaining release gates:** one supervised 90-second CH1
0-3 V / 0.10 A hardware demo with appropriate resistor and
actual front-panel original-state restoration/LOCAL check;
CV/CC live mode validation is optional and must never be
claimed from offline LSR event tests. User may take screenshots
during the same short session; no actual user screenshots
have been supplied. There is no hardware power-loss,
physically full-disk, multi-hour or 1000-hour endurance claim.

**Branch comparison verified:** `dev` is 235 commits
ahead of stable `main`, but behind by one v13.5 release
merge commit (`7d5b393`). Do not assume fast-forward
or rebase casually; prepare/review a standard PR when
user approves. `main` was confirmed unchanged at
`7d5b3931404a9630c0343808e3ac7f695b289516`.
No merge or tag has been created. Retain user-local
untracked `profiles/18.csv` untouched.

**Next user action:** instructions are consolidated in
`docs/HARDWARE_ACCEPTANCE_v13_6.md`. One short test with
optional pause/manual/resume is enough for this revision.
After reporting results and approved screenshots, update
README with actual evidence and request explicit release
approval before main merge.


## 2026-11-22 — Stage A offline reliability and v13.6 release preparation

User explicitly authorised completing all feasible offline development
and validation on `dev`, then delivering **one optimised hardware
checklist**, with CSV profiles for future README screenshots. Stable
`main` remains v13.5 and MUST NOT be changed/merged/tagged before
explicit approval. User local untracked `profiles/18.csv` is not
modified. Independent Rigol_capture repository remains untouched.

**Source changes:**
- Runner `scripts/cpx400dp_run_enhanced.py`: new
  `RecordingWriteFailure` exception and guarded `log()` boundary.
  The first real CSV `writerow()` or `flush()` exception during
  normal execution aborts into the existing `finally` restoration.
  During cleanup, subsequent log writes are disabled after first
  failure so a disk exception cannot suppress configured
  `finish_channels()`, physical readback or last `LOCAL` send.
  Nonzero result and explicit incomplete-recording warning; do not
  auto-report incomplete measurement CSV. The discovery event was
  moved inside the cleanup-protected try. Nested diagnostic handlers
  cannot silently continue once a logging failure has been recorded;
  heartbeat checks fail the run. End summary never reports success
  if CSV writing failed. No new SCPI commands or changed restore
  targets, setpoint timing or NetworkManager configuration.
- Post-run CSV report eligibility test uses a streaming
  `any(DictReader(...))` instead of loading every CSV event.
- Offline read-only `scripts/cpx400dp_archive.py`: opt-in ZIP
  containing raw measurement CSV, matching HTML report, associated
  `_report_data` JS chunk folder and optional console log;
  SHA-256 manifest and verified ZIP, no source deletion, no
  overwrite, atomic publish via hardlink on supported Linux FS.
  This is NOT an automatic retention policy or crash backup.
- `tests/test_v13_6_log_write_failures.py`: simulated ENOSPC
  failure during active setpoint logging, cleanup
  `final_state_verified`, and post-LOCAL command summary;
  mocks enforce final restoration before final LOCAL and nonzero
  failure. Expanded offline example tests and archive tests.
- `tests/browser_report_smoke.py` and new
  `browser_report` job in `.github/workflows/offline-tests.yml`:
  install temporary Chromium/Playwright in GitHub Actions ONLY,
  generate synthetic 1000-hour CSV, open HTML via file://,
  jump to 50 ms peak at t=3599950.05, assert local chunk load,
  measured V axis peak and cursors, and upload a 5-day
  SYNTHETIC browser screenshot artifact. No user-local
  dependency changes. Headless browser and Python suites
  both passed previously on run `45033144797`.
- Screenshot-oriented `profiles/examples/release_demo_90s_preview.csv`:
  dual-channel OFF-output 90s GUI preview, never needs PSU.
  `profiles/examples/hardware_demo_90s_REQUIRES_LOAD.csv`:
  optional supervised CH1 0-3 V / 0.10 A 90s run, originally
  OFF state restored; requires suitable resistor. These are
  clearly distinct and not to be mistaken for a 1000h
  hardware test.

**Release preparation:** README rewritten to reflect actual
features, report companion files and known limits. Added
`docs/HARDWARE_ACCEPTANCE_v13_6.md` (single supervised
90s hardware session + optional screenshots), and
`docs/RELEASE_CANDIDATE_v13_6.md` (release gates,
comparison/review requirements, no-merge policy).
`docs/RECORDING_RECOVERY.md` now documents checked archiving;
`docs/BACKLOG.md` separates complete offline gates from
remaining hardware and release blockers.

**Validation classification:** offline CI success is **not**
live PSU/ENOSPC or power-loss validation. Prior verified
address persistence and live IDN remain genuine user
hardware evidence. Screenshot artifact is synthetic and
must be labelled as such; user desktop/real run screenshot
assets have not been supplied and must not be invented.
No automatic backup/retention deletion or unattended
multi-day safety guarantee.

**Next action after final CI:** check full Python + Chromium
jobs both PASS on latest `dev` SHA, update CI evidence.
User should do only one supervised 90-second load test
if hardware acceptance is desired, with optional brief
pause/manual/resume and screenshot capture during same
session. Verify physical final V/A/enable state and LOCAL
on actual front panel and send concise results; no
41-day test, disk-fill or unsafe power interruption.
Await explicit approval before `dev` -> `main` merge.


## 2026-11-17 — Recording-audit hardware-log acceptance and classification refinement

User ran new read-only `cpx400dp_recording_audit.py` on
`reports/18_measurements_20261117_204309_699555.csv`:
7,334 events, 1,218 readbacks, 0 readback_error, both CH1
and CH2 with `final_state_verified`, and `local_sent`;
original audit classified LOGGED FINAL VERIFICATION.
This is real-log parsing acceptance only; do **not** infer
physical output state or an independent LOCAL readback.

User then audited the entire `reports/` directory: **21**
CSV files total. Of these, **12** were classified LOGGED
FINAL VERIFICATION, **6** classified INTERRUPTED, and
**3** contained zero event rows. All six INTERRUPTED
logs reported both channel verification events and a
`local_sent` event; those may represent controlled Stop
with successful logged cleanup rather than missing
restoration. The original label "STATE MUST BE CHECKED"
was insufficiently specific. The old output shows
presence but does not establish event ordering.

Implemented audit refinement on `dev`: track event row
ordering. For interrupted/fault-abort logs, show
`LOGGED CLEANUP VERIFIED (NOT PHYSICAL CONFIRMATION)`
**only if** `final_state_verified` for every observed
channel and `local_sent` are recorded **after the last**
interruption/fault marker; otherwise show
`CLEANUP NOT CONFIRMED BY LOG`. This preserves the
interrupted/fault status instead of incorrectly recasting
it as ordinary completion. Zero-event CSVs are now
separately labelled `EMPTY LOG (NO EVENTS RECORDED)`.
Errors labelled inspection errors. Added tests covering
ordering, missing per-channel verification, zero-event
files and original complete cases.

**Implemented and offline tests pending full CI at docs
time**; refined labels have NOT yet been re-run on the
user's 21 real CSVs. No PSU commands, file mutation,
automatic reconnection or recovery are involved.

Next optional user-side validation: pull dev and rerun
the read-only audit on `reports`; no PSU hardware
action is required. Earlier user-local untracked
`profiles/18.csv` must remain untouched.


## 2026-11-17 — CI PASS for runtime storage monitor, recording audit and examples

Full GitHub Actions offline regression `44173240184` on
`dev` commit `abc23813dd9b85c119e9f5f1952ec3b3de369aed`
**completed successfully**. This is the first completed
full-suite run including the runtime disk-warning code, read-only
recording audit and all three new long preview examples and tests.
Previous intermediate runs were cancelled by branch concurrency
when superseded by later commits. No hardware experiment or
physical full-disk/reboot/failure recovery validation was
performed or claimed.

**Next requirements:** preserve `main` stable v13.5; never
promote without explicit approval. A runtime warning is not
space reservation or an automatic safe stop. A CSV audit is
not a proof of actual hardware output/LOCAL. Existing CSV
write failure safety and asynchronous loss-of-power behavior
remain unverified; design and test separately. No automatic
old-CSV deletion policy has been introduced.


## 2026-11-17 — Long-run runtime storage warnings, recording audit and examples

Per user instruction, continued offline-only `dev` development
without asking for routine tests. No PSU network, SCPI, output,
restoration, LOCAL or Rigol source changes.

**Implemented in source:**
- `scripts/cpx400dp_storage.py`: added `DiskSpaceMonitor`.
  Checks output volume free bytes read-only and at most once per
  30 seconds. Prints advisory `[STORAGE WARNING]` at/below
  a 512 MiB reserve, repeating no more often than once per
  five minutes. Probe errors suppress warnings instead of
  interfering with PSU work. The monitor cannot reserve space,
  detect all disk failure modes or guarantee successful CSV writes.
- `scripts/cpx400dp_run_enhanced.py`: instantiated monitor
  within `execute` and checks during heartbeat paths; it emits
  messages only and never changes setpoints, stops the profile,
  changes outputs, disables current safeguards or changes
  restoration/LOCAL-last code.
- `scripts/cpx400dp_recording_audit.py`: read-only streaming
  inspector for CSV files or a results directory. Summarises
  observed readbacks, missing final/LOCAL event markers, interrupts,
  fault events, last timestamp, and explicitly marked synthetic
  files. Never contacts hardware or deletes/edits recordings.
  Even an apparently complete log does not prove physical
  outputs or LOCAL.
- `profiles/examples/long_24h_step_preview.csv` (24h, 5
  keyframes, one channel), `long_7d_linear_preview.csv`
  (7d, 8 keyframes, both channels), and
  `long_1000h_sparse_preview.csv` (1000h, 11 keyframes,
  two channels). All include enable=0 across their keyframes
  and restore=true; preview-only, not authorised unattended runs.
- A ZIP was generated for the user with all three sample
  profiles, README, and an offline-only synthetic 1000-hour
  measurement CSV of about 120,000 readbacks and a 50 ms
  synthetic transient near second 3,599,950.05. The large
  fictional CSV is not committed to GitHub. Its simulated
  `final_state_verified` and `local_sent` records must never
  be mistaken for real hardware validation.

**Regression tests:** new long-examples parser test, new
recording-audit classification tests, expanded storage monitor
tests. GitHub CI must be checked after final commit; don't
claim unobserved hardware acceptance.

**Limitations and next work:** no automatic deletion,
log retention policy or crash-safe resume. Existing disk-full
CSV writer exceptions could still interfere with cleanup logging;
must design dedicated safety-aware failure behaviour before
unattended endurance claims. This change provides monitoring
and post-run evidence inspection, not proof that an interrupted
PSU automatically reaches a safe electrical state. Use local
front panel inspection after unplanned shutdown. See
`docs/RECORDING_RECOVERY.md` and
`profiles/examples/README.md`.

User local untracked `profiles/18.csv` remains untouched.


## 2026-11-17 — Final streaming-report CI acceptance

**PASS:** GitHub Actions CPX400DP offline regression run
`44171162141` on `dev` commit
`ed60442dfaf5a53727267f49f81de1c854885ac0`
completed successfully. This includes the new large-CSV
reporting suite, synthetic extrema-preserving transient, 32000-row
memory-bound check, small-report compatibility, Node.js generated
chart JavaScript syntax check, and existing PSU safety/GUI
offline regressions. Earlier failed runs were due to an error
in the new test's regex, fixed before this success.

**Accepted level:** source implemented and offline CI passed;
not tested interactively in a desktop browser with a real
large log, and not hardware-endurance tested. No additional
hardware test required for offline report generation. Keep
HTML next to matching _report_data folder. Subsequent v13.6
backlog remains runtime disk/retention hardening and optional
desktop-browser visual inspection. User has authorised
autonomous offline development, but no change to physical
PSU control behaviour is authorised.


## 2026-11-17 — Streaming large-CSV report and indexed offline detail viewer

Per user instruction, continued v13.6 development automatically without
new bench tests. **No changes** to the separate Rigol_capture project,
PSU network settings, or any PSU SCPI/control/restore/LOCAL code.

Implemented a second report path in
`scripts/cpx400dp_report_stream.py`, automatically selected from
`scripts/cpx400dp_report.py` for measurement CSV files >=8 MiB.
Legacy small-CSV self-contained reports remain unchanged. CLI
`--stream` forces the new renderer for test fixtures.

Large report architecture: two sequential DictReader passes over
the original immutable measurement CSV; pass 1 derives run statistics,
initial/final output-state summary, power/energy, statuses, pause/
ramp/OFF annotations; pass 2 keeps per-channel plottable trace
chunks bounded to 4096 records and creates an extrema-preserving
overview with 1200 time bins (first/last/min/max). Generated
HTML embeds compact overview, per-channel time index and chart UI.
Separate sibling `*_report_data` folder holds numbered local JS
detail files. HTML loads only up to three intersecting chunks
for zoomed-in windows using script tags (works under file://
without HTTP server), with an LRU cache capped at six chunks.
New direct elapsed-time/window inputs allow navigating straight
to narrow 50 ms windows of long experiments. Chart retains
trace checkboxes, zoom/pan, cursor Delta-t/Delta-V, step-profile
vertical transitions, negative sample markers and output/pause/
ramp annotations. Power stats derive from logged sampled V*I.

Added `tests/test_v13_6_report_stream.py`: small-report
compatibility; forced streaming; synthetic CH2 transient/peak
preserved in full data and extrema overview; output sidecar
files and chart controls; 32000-row Python tracemalloc budget;
CLI/automatic threshold; error cases; generated viewer Node.js
syntax test when Node is available.

**CI note:** initial full offline suite on code/test commit
`563ba1de` passed (the Node syntax test had not been added).
Subsequent CI on `3abad48f` failed solely because the new
test's regex expected two scripts but captured one: the test
used doubled backslashes in a raw regex. Fixed in
`f8d3b045`. Do not mark the final state CI PASS until
a run containing this fix and final docs is successful.

See `docs/REPORT_STREAMING.md` for usage and limitations.
Not a live viewer; requires moving HTML and its _report_data
folder together; legacy small reports remain standalone.
Chunk manifest still grows with file size; metadata annotation
arrays are capped (10000 per channel, 100 diagnostics).
A full-screen overview is downsampled; narrow zoom loads true
samples. Two passes and additional disk files are necessary.
Does not provide in-run disk-space monitoring, crash recovery
or evidence of multi-day PSU hardware reliability. **Desktop
browser visual acceptance is not yet performed**, but no new
PSU bench testing is required because this change is offline
report generation only. The local untracked
`profiles/18.csv` must remain untouched.



## 2026-11-17 — v13.6 long-run disk capacity advisory (source implemented)

After successful address/interface persistence acceptance, resumed
long-duration recording work as directed. Reviewed backlog:
1,000-hour lazy scheduler and time-axis support already offline
implemented, but report generation still uses whole-CSV loading and
embedded full arrays; long-run disk monitoring remains incomplete.

Added `scripts/cpx400dp_storage.py` with pure read-only
`storage_forecast(output_path, duration_s, interval_s,
readback_interval_s, channel_count)`. It uses filesystem free
space at the measurement CSV destination, estimates an advisory
budget of 512 bytes for each expected setpoint/readback CSV event
across channels, plus 512 MiB of spare capacity. If the free
capacity is below that forecast, emits `[STORAGE WARNING]`
including rough budget/free/recommended capacity and clear
statement that the run is **not blocked**. Invalid inputs or an
unavailable disk probe suppress the advisory rather than
alter the established instrument workflow.

Integrated the call into `execute` in
`scripts/cpx400dp_run_enhanced.py`, before measurement CSV
open and before PSU socket/commands. No changes to profile
scheduler or profile/Manual Control output commands, readbacks,
restoration, or LOCAL-last safety behaviour. No network
changes and no changes to separate Rigol capture repository.

Added offline regressions in
`tests/test_v13_6_storage_forecast.py` for sufficient/insufficient
capacity, readback frequency sensitivity, invalid and unavailable
probe conditions and runner insertion order.

Commits include `f2d60a43` helper, `6336f5f6` runner,
`efbd33ff` tests and backlog follow-up.
**Source implemented, CI pending, NOT hardware validated.**
This is intentionally a pre-run advisory only; it neither
reserves space nor monitors disk mid-run, predicts exact
measurement and HTML output sizes, or makes unattended
1000-hour operation safe. Subsequent major task remains
streaming/bounded report generation and robust runtime
storage monitoring. User local untracked `profiles/18.csv`
must be left untouched.



## 2026-11-17 — PSU GUI verified-destination persistence hardware/UI acceptance PASS

User confirmed **both** the PSU IPv4 field and selected interface
are remembered across a full GUI close/relaunch on their Kubuntu
workstation, following the v13.6 change committed on `dev`.
Expected verified destination was `192.168.71.2` on D6000
`enx0c3796303396`, previously confirmed with live
read-only **Test connection**. This is real user-side GUI
persistence validation, not an electrical-output or runner test.

GitHub Actions `CPX400DP offline regression` run
`44166633012`, on head `f96db5cd80f1d16b7095ef648cbaf557e853e9e5`,
completed **successfully**. Other intermediate workflow runs
were cancelled due to newer commits; the final run passed.

**Status**: implemented, offline-CI-passed and on-hardware/UI
accepted. No further change needed for this feature.
Keep the independent Rigol_capture project untouched per user.
Local `profiles/18.csv` was reported untracked and must not be
modified or deleted without an explicit request.

**Next**: resume prioritised CPX400DP v13.6 feature development,
preserve verified profile/manual-control safety, do offline tests
before requesting additional hardware tests.


## 2026-11-17 — Return to PSU v13.6: persist last verified GUI destination

Per user direction, **do not modify the separate Rigol_capture project**.
Reviewed `scripts/cpx400dp_gui.py` on `dev`: GUI already used
`QSettings('CPX400DP', 'ControlGUI')` for output/profile paths, but
the PSU IPv4 field and interface combo were recreated blank/Auto at
each GUI startup, even after a successful **Test connection**. The
discovery layer has a separate last-PSU cache, yet the GUI does not
populate those widgets from it. This explains manual re-entry of
`192.168.71.2`.

**Source changes on dev:** in `Window.__init__`, read
`verified_psu_ip` and `verified_psu_interface` from per-user
QSettings; restore the address only if it passes IPv4 validation,
and restore interface only if it is present in the currently
enumerated combo. Missing interfaces fall back to Auto. No
startup connection attempt, route change, or instrument command.
In `connection_test_finished`, only for
`result.status == 'found'`, save the successfully identified
host/interface pair to QSettings and sync. A failed/ambiguous test
does not overwrite the last verified pair. Manual typing alone does
not persist without testing. Existing explicit IP override, CSV
fallback when blank, discovery, socket ownership, power-control
and restore/LOCAL semantics remain unchanged.

Added `tests/test_v13_6_verified_destination.py` as offline AST
regressions for restore, validation, success-only saving and
unchanged override paths. Commits:
`70e0e7f` implementation, `fc285949` tests,
`d87fe19b` import cleanup.
**Not yet hardware/UI validated.** Latest offline CI status
must be checked against final dev commit before marking CI PASS.
Next user validation: launch updated GUI, enter PSU address
192.168.71.2 and select D6000, run read-only Test connection;
close and reopen GUI and verify fields are prefilled with the
same verified destination, without any automatic probe on startup.
Test address edit or failed probe does not replace saved pair.
Do not use profile-run or manual-control for this acceptance.



## 2026-11-17 — Rigol capture GUI verified after static-network migration (hardware/application PASS)

User launched the separate `FLRHW/Rigol_capture` GUI on Kubuntu
after Rigol was configured at `192.168.70.2` on the independent
`192.168.70.0/24` link. User supplied the capture console:

```text
Instrument verified: RIGOL TECHNOLOGIES,DS1054Z,DS1ZA221303251,00.04.04.SP4
Network path: automatic system route
CH2: 434/434 points (100.0%)
CH2: wrote 434 of 434 acquired samples (decimate 1)
CH2: exported 434 rows, saved spacing 0.002 s (original spacing 0.002 s)
CH4: 714/714 points (100.0%)
CH4: wrote 714 of 714 acquired samples (decimate 1)
CH4: exported 714 rows, saved spacing 0.002 s (original spacing 0.002 s)
Saved: /mnt/Data/01_Engineering/01_Projects/301_Rigol_DS1054Z/Rigol_capture/captures/rigol_scopech2ch4.csv
Scope-relative timestamps only; no shared PC/PSU trigger timestamp.
```

**Validated by user-supplied console:** scope identity, automatic system
route, acquisition completion for CH2 and CH4, no export decimation,
2 ms sample spacing and CSV output. CH2 and CH4 returned different
sample counts (434 and 714); do not presume cause without examining
the separate Rigol_capture source, acquisition setup and CSV.
This does NOT prove sustained deep-memory transport reliability,
time synchronisation with PSU, or resolution of the independent
DSRemote `screen_thread.cpp line 783` issue.

Combined previous evidence: both dedicated NetworkManager profiles
came up after user-confirmed Kubuntu reboot; each instrument replied
4/4 to sourced pings; CPX400DP GUI read-only Test connection succeeded
at `192.168.71.2`. Network migration and basic application
connectivity are therefore **validated**, with any instrument-side
power-cycle persistence still a separate check. Do not conflate
Rigol_capture source with PSU_control. No new PSU software/code,
instrument settings, or network changes in this checkpoint.

**Next PSU_control focus:** return to v13.6 app work: inspect
current `dev` GUI IP/discovery persistence behaviour before
selecting a targeted usability improvement; run offline CI for
code changes and have user validate hardware-only tests.


## 2026-11-17 — Host reboot persistence PASS; PSU GUI Test connection PASS

User explicitly confirmed that the preceding dual-instrument `nmcli`,
sourced ping and default-route checks were performed **after Kubuntu
reboot**. The post-reboot report showed `Rigol-Direct` active on
`enp3s0f1`, `CPX400DP-Direct` active on
`enx0c3796303396`, Wi-Fi default via `wlp4s0`,
Rigol `192.168.70.2` answering 4/4 pings from
`192.168.70.1` and PSU `192.168.71.2` answering 4/4
from `192.168.71.1`. **Host reboot persistence PASS,
user-confirmed**; no further NetworkManager/IP changes needed
absent new evidence.

User also reports CPX400DP GUI **Test connection works** after manually
entering `192.168.71.2`. This is user-reported live application
connectivity at the new static PSU address. The exact `*IDN?`
response and diagnostic log were not supplied; do not infer
readback/runner/restore hardware tests from this brief connection
test. Manual IP entry was required for this test; retain investigation
of how the GUI remembers/prefills the new static IP and handles
auto-discovery as a usability enhancement, not a network-blocker.

**Outstanding gates:** Rigol waveform capture / identity test against
`192.168.70.2` via `enp3s0f1`; instrument-side reboot persistence
not yet confirmed; v13.6 software and offline CI to continue.
No source modifications or host/instrument settings were performed
during this documentation checkpoint. Stable `main` v13.5 and
development `dev` remain distinct.


## 2026-11-17 — Both direct static links and Wi-Fi confirmed concurrently

User supplied another read-only network report:
`nmcli -f NAME,DEVICE connection show --active` listed
`CPX400DP-Direct` on `enx0c3796303396`,
`Rigol-Direct` on `enp3s0f1`, and Wi-Fi
`CordeiroSuculento` on `wlp4s0` (plus `lo`).
Rigol sourced ping from `192.168.70.1` to
`192.168.70.2`: 4/4 replies, 0% loss, average
0.273 ms. CPX400DP sourced ping from `192.168.71.1`
to `192.168.71.2`: 4/4 replies, 0% loss, average
4.296 ms. Default route remains `via 192.168.0.1
dev wlp4s0 src 192.168.0.252`.

**Important evidence limit:** the user supplied requested post-reboot
commands' output but did not explicitly state that a reboot occurred.
Mark the active-profile and simultaneous IP reachability checks PASS;
host reboot persistence remains conditional/unconfirmed unless the
user confirms that the PC was restarted before these commands.
Do not overclaim. The next gate is GUI `Network settings → Test
connection` with PSU `192.168.71.2` / D6000; then Rigol
capture `192.168.70.2` / built-in NIC. No new software changes,
instrument commands or PSU output tests in this checkpoint.


## 2026-11-17 — Both instruments simultaneously reachable after Rigol NM down/up (PASS)

User enabled `connection.autoconnect=yes` on `Rigol-Direct`
UUID `6b03df6c-928c-4b8f-b646-43146b8ca419`, then explicitly
deactivated and reactivated that profile on `enp3s0f1`.
Both NM operations succeeded. Post-test:
- Rigol NIC `enp3s0f1`: NM `Rigol-Direct`, state
  `100 (connected)`, `192.168.70.1/24`.
- Rigol `192.168.70.2` from `192.168.70.1`: 4/4 ICMP
  replies (0% loss), min/avg/max = 0.196/0.276/0.330 ms.
- D6000 PSU NIC `enx0c3796303396`: NM
  `CPX400DP-Direct`, state `100 (connected)`.
- PSU `192.168.71.2` from `192.168.71.1`: 4/4 ICMP
  replies (0% loss), min/avg/max = 2.313/2.395/2.508 ms.
- Wi-Fi internet default remained `via 192.168.0.1 dev wlp4s0
  src 192.168.0.252`.

**Validated:** both dedicated, saved NM profiles now connect and
both instrument IPv4 addresses are reachable simultaneously;
Rigol profile survives deliberate down/up (PSU profile separately
passed earlier). The original unbound `Wired connection 2` was
previously retained with autoconnect disabled. No changes to
instrument electrical outputs or control source code.

**Remaining:** no physical cable disconnect test; no host reboot
or instrument power cycle persistence verified; no SCPI
identity/control or Rigol waveform-capture test on the new
addresses; no PSU GUI discovery/address persistence validation
on 192.168.71.2. Next sensible step is read-only application
identification tests with each direct IP, then reboot/link
persistence checks when safe. Preserve stable main v13.5,
and document hardware versus application testing separately.


## 2026-11-17 — Rigol new static IPv4 physically reachable (PASS)

User configured DS1054Z LAN settings and reported sourced ping
`ping -c 4 -I 192.168.70.1 192.168.70.2`: **4/4 replies,
0% packet loss**, RTT min/avg/max 0.184/0.257/0.412 ms,
TTL 255. This validates scope network reachability at
`192.168.70.2` from built-in Ethernet host
`192.168.70.1`. It does not by itself prove instrument
settings' power-cycle persistence, SCPI/waveform capture,
DSRemote reliability, or end-to-end software behaviour.

At previous checkpoint, `Rigol-Direct` UUID
`6b03df6c-928c-4b8f-b646-43146b8ca419` was manually
activated, but `connection.autoconnect=no` was retained from
initial staging. **Next instruction (not yet completed):**
enable autoconnect on that exact UUID, explicitly cycle NM
down/up on `enp3s0f1` with applications closed, then verify
both scope `192.168.70.2` and PSU `192.168.71.2`
sourced pings, active profiles and unchanged Wi-Fi default.
Keep unrelated profiles unchanged. PSU dedicated connection
already passed down/up test. Later test physical link restart
and host/instrument reboot plus instrument application discovery
on fixed addresses. No code changes this checkpoint.


## 2026-11-17 — Dedicated Rigol PC-side NM profile activated and route validated

User created `Rigol-Direct` UUID
`6b03df6c-928c-4b8f-b646-43146b8ca419` bound to
`enp3s0f1` / MAC `18:3d:2d:3c:93:6d`,
`ipv4.method=manual`, `192.168.70.1/24`,
`ipv4.never-default=yes`, IPv6 disabled,
`autoconnect=no` (initial staging). User activated it explicitly
using `sudo nmcli connection up Rigol-Direct ifname enp3s0f1`.
Command succeeded. `ip -br -4 addr` shows
`enp3s0f1 UP 192.168.70.1/24`; NM reports state 100
and active `Rigol-Direct`. Kernel routing of proposed scope
destination `192.168.70.2` from host `192.168.70.1`
selects `enp3s0f1`. PSU traffic `192.168.71.2`
still selects D6000 `enx0c3796303396` from `192.168.71.1`;
Wi-Fi default remains via `192.168.0.1` on `wlp4s0`.

**Status:** PC-side Rigol interface/routing configuration PASS.
Scope-side address `192.168.70.2/24` is PROPOSED and not yet
reported applied. No ping to Rigol new address or Rigol application
test yet, nor reconnection/reboot validation. Do not claim complete
Rigol network migration. Next: from Rigol front panel
`Utility → IO Setting → LAN Conf.`, set DHCP off,
Auto IP off, Static IP on; address `192.168.70.2`, mask
`255.255.255.0`, gateway zero/blank as interface permits;
Apply; check current IP and ping. Rigol DS1000Z guide documents
Power-on Recall=Last requirement for persistent manual addressing;
verify choice and do not needlessly change other oscilloscope settings.
After link success, enable Rigol-Direct autoconnect and test saved
profile reactivation. PSU configuration remains unchanged.


## 2026-11-17 — Rigol /24 active-subnet conflict check PASS; profile preparation instructed

User supplied live `ip -br -4 addr`, `ip -4 route show table all`,
`nmcli` inventory and `ip route get 192.168.70.2`.
Active interfaces are Wi-Fi `wlp4s0` `192.168.0.252/24`
(default via `192.168.0.1`), PSU dock `enx0c3796303396`
`192.168.71.1/24`, and loopback. No current IPv4
address or route overlaps proposed `192.168.70.0/24`.
With no Rigol route yet, `ip route get 192.168.70.2`
predictably selects the Wi-Fi default gateway; this is not
evidence of a conflict. Rigol NIC `enp3s0f1` remains
NM state 30 disconnected. Existing generic `Wired connection 2`
is saved but inactive. Active routing check does not exclude
future/disconnected VPN or other saved address conflicts.

**Next user instruction (not yet executed):** use NetworkManager rather
than a transient `ip addr` for the Rigol host. Create inactive
`Rigol-Direct` profile, `ifname enp3s0f1`, MAC
`18:3d:2d:3c:93:6d`, static host
`192.168.70.1/24`, `ipv4.never-default=yes`,
IPv6 disabled and initial `autoconnect=no`.
Activate on the built-in NIC, verify scope route to proposed
`192.168.70.2`, ensure PSU route and Wi-Fi default unchanged.
Only after PC-side verification set Rigol IP from front panel.
**No Rigol profile creation, source change, scope settings change,
or hardware validation has occurred in this checkpoint.**


## 2026-11-17 — PSU dedicated NM profile down/up hardware validation PASS

User explicitly deactivated and reactivated `CPX400DP-Direct` UUID
`a6fa9a7a-e871-4752-8c85-60e4000fe42a` on Dell D6000
`enx0c3796303396` using `nmcli connection down` and
`nmcli connection up ... ifname enx0c3796303396`.
Both commands reported success. Post-activation `nmcli`
showed `GENERAL.CONNECTION=CPX400DP-Direct` and NM state
`100 (connected)`; `ip -br -4 addr` showed `192.168.71.1/24`.
Sourced ping `ping -c 4 -I 192.168.71.1 192.168.71.2` returned
**4/4 responses, 0% loss**, average 3.595 ms. The Wi-Fi default
route remained `default via 192.168.0.1 dev wlp4s0`.
**Hardware/network PASS:** the saved profile survives manual NM
down/up and restores PSU reachability. This does not prove PSU SCPI
after reconnect, physical cable disconnect, PSU reboot, host reboot
or long-term automatic autoconnect behavior.

**Next planned:** Rigol dedicated static subnet 192.168.70.0/24,
host enp3s0f1 (MAC 18:3d:2d:3c:93:6d) at 192.168.70.1/24,
scope at 192.168.70.2/24, no gateway. First read-only check for
route conflicts and interface address, then temporary host address
and route verification before changing instrument settings. Avoid
touching validated CPX400DP-Direct and Wi-Fi profiles. No Rigol
configuration change was reported at this checkpoint.


## 2026-11-17 — Saved D6000 PSU profile activation hardware PASS

User executed on Kubuntu:
- Disabled autoconnect for the original unbound `Wired connection 2` UUID `4158f5eb-2e6b-3274-8f74-bb2a48c41126` (profile retained).
- Enabled autoconnect for dedicated `CPX400DP-Direct` UUID `a6fa9a7a-e871-4752-8c85-60e4000fe42a`.
- Successfully activated new UUID using `nmcli connection up ... ifname enx0c3796303396`.

User verification:
- D6000 `enx0c3796303396` UP, `192.168.71.1/24` **only**; former roaming `169.254.10.1/16` gone.
- NetworkManager `GENERAL.CONNECTION=CPX400DP-Direct`,
  state `100 (connected)`.
- `ping -c 4 -I 192.168.71.1 192.168.71.2`: **4/4 replies**,
  0% loss, 3.481 ms average. Instrument at static 192.168.71.2 responds.
- Default route still `192.168.0.1` via Wi-Fi `wlp4s0`
  (`192.168.0.252` source).
- No PSU output or SCPI control tests performed in this step.

**Status:** persistent **saved profile created and active, hardware network
connectivity PASS**. Explicit profile reconnect, physical link reconnect,
device/host reboot persistence, SCPI *IDN? and runner discovery on the new
IP are **NOT YET VERIFIED**. Old profile remains present with autoconnect
disabled for rollback; do not delete without a later housekeeping decision.

**Next instructed test:** with PSU GUI idle, `nmcli connection down` then
`nmcli connection up` the dedicated UUID on the dock, followed by
active-profile/address/4-ping/default-route verification. This deliberately
interrupts the Ethernet connection and must not be used while profiles
are running. Thereafter proceed with independent Rigol static subnet
migration. Keep `main` unaffected.


## 2026-11-17 — Dedicated PSU NM profile created; activation still pending

User completed backup directory and output snapshot
`~/PSU_network_backup/old_ethernet_profile.txt` via
`nmcli connection show` for original generic Ethernet profile
UUID `4158f5eb-2e6b-3274-8f74-bb2a48c41126`.
This is a text snapshot, **not** a complete restorable NM keyfile.
A new saved Ethernet profile **CPX400DP-Direct** was created
with UUID `a6fa9a7a-e871-4752-8c85-60e4000fe42a`;
bound to interface `enx0c3796303396` and MAC
`0c:37:96:30:33:96`; manual host IPv4
`192.168.71.1/24`, never-default=yes, IPv6 disabled,
autoconnect=no at creation. Profile listing confirms it is
**inactive** and `Wired connection 2` is still active
on the D6000. No NM profile switch or reboot yet.

**User next action, explicitly directed:** with PSU GUI idle,
disable autoconnect on old UUID (preserve profile), enable
autoconnect on new UUID, activate new UUID specifically on
D6000, and check resulting `ip -br -4 addr`, NM active
connection, sourced ping to `192.168.71.2`, and Wi-Fi
default route. If switching fails, recover via original UUID
after restoring autoconnect; do not delete old profile.
This step has NOT been reported as completed. No change
to PSU output or software in this checkpoint. Static PSU
IP and HTTP page were previously verified; reboot
persistence not yet tested.

## 2026-11-17 — PSU static address and web interface validated

User supplied screenshot of CPX400DP's live configuration page at the
new network configuration after successfully pinging 192.168.71.2
from temporary host 192.168.71.1/24 via D6000 (4/4 ICMP replies).
Screenshot shows DHCP unchecked, AUTO-IP unchecked, STATIC checked,
IP 192.168.71.2, netmask 255.255.255.0, gateway 0.0.0.0,
both DNS 0.0.0.0, TCP Socket Full Control. User reports the web
interface loaded at new IP. This is physical verification of
network connectivity and displayed static configuration, **not**
yet SCPI *IDN? validation, instrument reboot persistence,
NetworkManager reboot persistence, or PSU control validation.

Next: establish a saved dedicated hardware-bound D6000 NM profile
for host 192.168.71.1/24 (no gateway, never-default=yes), and ensure
the unbound generic Wired connection 2 UUID
4158f5eb-2e6b-3274-8f74-bb2a48c41126 cannot autoconnect to
the wrong NIC. Back up existing NM configuration before changes,
obtain authorization for profile writes, stage/activate in safe
sequence with rollback. Wi-Fi unchanged. Once stable, set up Rigol
on independent 192.168.70.0/24 with its own bound profile.
The host currently relies on an **ephemeral** ip addr add; no saved
NM profile migration or reboot test has passed yet.

## 2026-11-17 — First real static-IP PSU connectivity test PASS (temporary PC address)

User verified `enx0c3796303396` holds both the old
`169.254.10.1/16` (NetworkManager) and a **temporary** manually
added `192.168.71.1/24`. `ip -4 route get 192.168.71.2
from 192.168.71.1` selects `enx0c3796303396`.
User's `ping -c 4 -I 192.168.71.1 192.168.71.2` returned
**4/4 replies, 0% loss**, average 3.257 ms. This is positive
physical connectivity evidence for the PSU at new proposed static
IP `192.168.71.2`; it is NOT yet proof of HTTP/SCPI reachability,
reboot persistence, or correct final DHCP/Auto-IP flag state.

An earlier test failed because the temporary PC address had disappeared,
likely on NetworkManager profile reactivation; the user re-added it
successfully. **No persistent NetworkManager changes yet**, and the
old generic unbound `Wired connection 2` is still a configuration
hazard. Next: confirm HTTP page at 192.168.71.2, then stage a narrowly
scoped hardware-bound saved dock profile with rollback, followed by
Rigol migration, before any reboot acceptance testing.

## 2026-11-17 — PSU web Configure page visually confirmed (no changes)

User supplied a screenshot of the live CPX Series CONFIGURATION PAGE.
It visibly contains all three checked TCP/IP Configuration Mode options:
`DHCP >>`, `AUTO-IP >>`, and `STATIC`. The displayed static
configuration fields show IPv4 `192.168.0.100`, mask
`255.255.255.0`, gateway `0.0.0.0`, and both DNS servers
`0.0.0.0`. Page instruction: static settings are used if automatic
configuration is disabled or servers not available; `Change` is
required to activate changes and some fields require power-cycling.
These fields DO NOT prove the live PSU IP is 192.168.0.100; the
earlier observed Auto-IP instrument address was 169.254.51.7.
No settings were changed.

Decision guidance: separate static /24 networks are recommended for
both fixed-position instruments, but configuring both static is not
strictly necessary. One static and one Auto-IP can work with correctly
scoped NIC profiles but retains dynamic-address and 169.254/16 issues.
Proposed (NOT APPLIED): Rigol 192.168.70.2 / host 192.168.70.1;
PSU 192.168.71.2 / host 192.168.71.1; mask 255.255.255.0,
no gateway/DNS on isolated links, DHCP and Auto-IP disabled.
Avoid the screenshot's preset 192.168.0.100/24 because active
Wi-Fi is already 192.168.0.0/24. Before any application, confirm
no address overlap with other networks/VPNs, ensure host profiles
are prepared for migration, and keep recovery procedures ready.
No OS/profile/firmware/PSU changes were performed; validation
remains screenshot-only, not static-IP hardware validation.

## 2026-11-17 — Manufacturer documentation verified; network option decision

Reviewed the *CPX400DP Instruction Manual Issue 1*
(https://resources.aimtti.com/manuals/CPX400DP_Instruction_Manual-Iss1.pdf),
Aim-TTi's CPX Series firmware release notes
(https://www.aimtti.com/resources/cpx-series-interface-firmware-file),
and the Rigol DS1000Z User's Guide
(https://www.batronix.com/pdf/Rigol/UserGuide/DS1000Z_UserGuide_EN.pdf).
Do not presume implementation of every feature on the user's actual
firmware without visual confirmation.

**CPX400DP:** official manual's LAN section states DHCP first, Auto-IP
after a 30 s DHCP timeout, configurable basic web server, and recessed
rear-panel LAN RESET to restore factory networking. The current unit's
*IDN? previously reported interface firmware **4.06**. Aim-TTi's
release notes say v4.12 fixed intermittent LAN dropouts; v4.20 improved
continuous-traffic robustness; and **v4.22 fixed the NETCONFIG,
IPADDR and NETMASK remote commands**. Therefore do NOT use SCPI
network-configuration writes on this v4.06 instrument. Prefer inspecting
the supported web Configure page before attempting manual addressing.
No firmware update is proposed as a prerequisite.

**Rigol DS1054Z:** DS1000Z User's Guide, System Function Setting,
LAN configuration pp. 14-3 to 14-5, explicitly documents DHCP,
Auto IP and Static IP, editable IP/mask/gateway/DNS, Apply,
Initialize recovery, and nonvolatile IP/mask storage; for power-on
persistence Power-on Recall must be Last and DHCP/Auto IP off.

**Tradeoffs:** Auto-IP needs no instrument configuration but two
independent NICs sharing 169.254/16 create route ambiguity and changing
Auto-IP addresses invalidate pinned routes. DHCP on a shared router
can simplify setup but changes topology / requires a DHCP server
and may require reservations. Two dedicated static /24 links on
distinct subnets avoid ambiguous routes and DHCP dependency, but
require one-time instrument and NM changes and are less portable.
Proposed example ONLY: Rigol PC 192.168.70.1, instrument
192.168.70.2; PSU PC 192.168.71.1, instrument
192.168.71.2; masks /24, no instrument-network gateway.
Check conflicts with other active/VPN networks first.

**Safety / operational status:** this research changes NO instrument,
OS, code, profiles, PSU outputs or firmware. Next checkpoint:
view PSU's actual HTTP Configure page *without saving* and
read Rigol LAN menu status; assess static configuration then
prepare safe per-instrument staged activation and rollback.
Keep device configuration changes behind explicit user approval.


## 2026-11-17 — Confirmed NIC MAC identities and simpler preferred design

User confirmed physical interface MACs: Rigol-side built-in
`enp3s0f1` = `18:3d:2d:3c:93:6d`; PSU-side Dell
D6000 `enx0c3796303396` = `0c:37:96:30:33:96`.
These are NIC identities, not instrument MAC addresses.

User raised valid concern over repeated diagnostics and complexity.
Prefer a **simple, conventional static-IP configuration on separate
non-overlapping subnets**, subject to verifying device settings and
explicit authorization: illustrative Rigol link host
`192.168.70.1/24`, scope `192.168.70.2/24`;
PSU link host `192.168.71.1/24`, CPX400DP
`192.168.71.2/24`. These are PROPOSED, not current addresses.
Both devices' documentation supports configurable static LAN
addressing. Two separate MAC/interface-bound NetworkManager
profiles would use `never-default=yes` with no gateways and
autoconnect enabled, removing competing 169.254/16 route ambiguity.
Existing generic `Wired connection 2` must be safely constrained or
disabled from roaming; back up UUID first. Preserve Wi-Fi.

**Still NOT APPLIED:** no host profile, routing or instrument-side
changes, and no new code or hardware validation. Avoid further
piecemeal diagnostics unless needed for execution/recovery.
Stage any instrument-side static-IP transition with reversible
steps because changing an instrument address breaks its active link
until corresponding host settings are ready.

## 2026-11-17 — Confirmed roaming Ethernet profile; runtime route misdirection

User supplied read-only saved-profile and kernel routing diagnostics. The only
active Ethernet profile `Wired connection 2` (UUID
`4158f5eb-2e6b-3274-8f74-bb2a48c41126`) has NO
`connection.interface-name` or `802-3-ethernet.mac-address` binding,
`connection.autoconnect=yes`, `ipv4.method=manual`,
`ipv4.addresses=169.254.10.1/16`, no `ipv4.routes`,
`ipv4.never-default=no`, and `ipv4.route-metric=-1`. The
profile is currently active on the **D6000** `enx0c3796303396`,
which now owns `169.254.10.1/16` instead of its previously observed
`169.254.51.8/16`. The built-in Rigol NIC `enp3s0f1`
reports carrier=1 but NM state 30 disconnected, with no IPv4 address
shown in `ip -br -4 addr`. Both
`ip route get 169.254.179.79` (Rigol) and
`ip route get 169.254.51.7` (PSU) select the D6000 with
source `169.254.10.1`. The internet default route remains via
Wi-Fi `wlp4s0` and gateway `192.168.0.1`.

**Confirmed configuration fault:** the unbound autoconnect
`Wired connection 2` profile is being applied on the wrong
Ethernet adapter and can roam. The present routing is wrong for
the Rigol. This does NOT by itself prove whether the PSU currently
responds or whether either instrument's Auto-IP address remains
unchanged; no live probe was performed.

**Proposed next migration (NOT APPLIED):** back up that exact UUID,
retain/replace it only with an interface- and MAC-bound Rigol
profile using `169.254.10.1/16` and
`169.254.179.79/32` route; create a separately bound D6000
profile using `169.254.51.8/16` and
`169.254.51.7/32` route. Set `never-default=yes`
on both; avoid any generic autoconnect fallback, preserve Wi-Fi,
verify actual NIC MACs and current instrument IPs before changes,
and prepare scoped rollback before any activation. A profile on
an inactive NIC is NOT evidence of an OS change having occurred.
Instrument Auto-IP addresses may change, invalidating hardcoded
host routes; fixed independent subnets may be considered later.

**Status:** read-only diagnosis only. NO OS, PSU, GUI or source changes,
reboots, instrument commands, or new hardware validation.
User approval required before configuration modifications.
The earlier `NETWORK_PERSISTENCE_PLAN.md` proposal MUST NOT be
applied verbatim until corrected for the roaming UUID.

## 2026-11-17 — Saved-profile inventory contradicts earlier NIC assignment

User ran read-only `nmcli` checks on the M75q. Current inventory shows
`Wired connection 2` UUID `4158f5eb-2e6b-3274-8f74-bb2a48c41126`
**active on D6000** `enx0c3796303396` (NM state 100 connected),
not on the Rigol NIC. Rigol `enp3s0f1` is NM state 30 disconnected,
with no active connection. Wi-Fi `wlp4s0` is connected via its
existing profile. The listing does not reveal whether the Rigol is
powered or linked, the saved profile interface binding, or persisted
IPv4 addresses/routes.

**Safety correction to prior plan:** do NOT modify `Wired connection 2`
to install the Rigol host route based on its name. The earlier report
associated that name with the Rigol; its current UUID and binding must
be independently verified before any configuration change. No
NetworkManager modifications, interface activation, reboot, PSU
commands, or code changes performed in this checkpoint.

**Next read-only checks:** inspect UUID `4158f5eb-2e6b-3274-8f74-bb2a48c41126`
for `connection.interface-name`, `802-3-ethernet.mac-address`,
`ipv4.method`, `ipv4.addresses`, `ipv4.routes`,
`ipv4.never-default`, `connection.autoconnect`; inspect
`ip -br -4 addr`, `ip -4 route`, and `ip -4 route get` to both
instruments. Determine physical carrier on `enp3s0f1` and whether
another saved connection is available for it. Re-design as separately
hardware-bound profiles with scoped rollback only after fresh
evidence and explicit approval.

## 2026-11-17 — Both-instruments-on persistence assessment and reviewed proposal

User repeated GUI **Assess persistence** with Rigol and PSU powered on.
Both link-local `169.254.0.0/16` routes were present.

- Rigol `enp3s0f1`: `169.254.10.1/16`, NetworkManager
  `100 (connected)`, profile `Wired connection 2`,
  saved `ipv4.method=manual`, saved address `169.254.10.1/16`,
  autoconnect yes.
- D6000 `enx0c3796303396`: `169.254.51.8/16`,
  NetworkManager `100 (connected (externally))`, runtime
  connection `enx0c3796303396`, not proven persistent.
- No saved Rigol host route was listed in the active report.
  An earlier temporary `169.254.179.79/32` exception had fixed
  incorrect scope routing; its current presence is not established
  by this report.

**Action on `dev`:** authored
[NETWORK_PERSISTENCE_PLAN.md](NETWORK_PERSISTENCE_PLAN.md)
with a *review-only* approach: preserve the Rigol NM profile,
back up verified profiles/UUIDs, save a Rigol /32 host route,
create a unique hardware-specific manual-address dock profile
with a PSU /32 route, preserve Wi-Fi, verify routing/identity,
and provide scoped rollback. Addresses remain dependent on the
instruments' Auto-IP assignments; plan does not guarantee
indefinite persistence. Existing NM profiles must be inventoried
before a future actual migration.

**NOT IMPLEMENTED / NOT HARDWARE-TESTED:** no NetworkManager
profile creation, activation, saved route changes, reboot,
instrument IP reconfiguration or OS changes were performed.
User's explicit approval is required for those operations.
`main` remains v13.5. DSRemote waveform-reading issue stays
deferred.



## 2026-11-17 — User persistence preflight and follow-up

**User-provided first read-only report** listed only D6000
`enx0c3796303396`, address `169.254.51.8/16`,
NetworkManager state `100 (connected (externally))`, apparent
connection `enx0c3796303396`. Thus address persistence is
**not established**. Rigol `enp3s0f1` was absent from the *active
link-local route* list; that does not prove the NIC is missing,
and no inference about its power state is made. The known older
two-/16 conflict remains unresolved. User did not run any
network-mutating commands or the GUI Prepare adapter.

**Implementation on dev:** amended the read-only preflight to
also enumerate Ethernet-style interfaces from the IPv4 address
snapshot even if they have no current link-local route, showing
their current NetworkManager state/profile. This avoids hiding a
Rigol interface when its `169.254/16` route vanishes. Added
mock regression for the route-free Rigol case, with Wi-Fi excluded
from this inventory. A heuristic NIC naming filter is for
reporting only, not configuration or authorization.
No system networking changes, PSU commands or automatic
persistent profile migration were made.

**Next user checkpoint:** with both physical instruments powered
on, repeat Network settings → Assess persistence and share the
full report. Then develop a proposed reversible route/profile
configuration for the actual connected setup; user approval
still required before applying OS changes. Do not press
Prepare adapter on the externally configured dock.



## 2026-11-17 — Network persistence preflight (source implemented)

In response to the user's direction to proceed without waiting for
additional hardware testing, a new **read-only** persistence assessment
was added on `dev`:

- `scripts/cpx400dp_network_preflight.py` inspects installed IPv4
  routes and addresses, then consults NetworkManager's active
  connection/state and saved IPv4 methods, explicit addresses,
  routes and autoconnect values on affected link-local interfaces.
- Reports overlapping links, externally configured adapters (the
  previously observed D6000 state), missing saved profile host routes
  (e.g., the temporary Rigol `169.254.179.79/32` exception),
  and effective kernel routing for an entered PSU IP.
- `scripts/cpx400dp_gui.py` adds **Assess persistence** in Network
  settings. A `QThread` runs the bounded read-only commands so Qt
  stays responsive; an independently scrollable report dialog presents
  the results. The action never creates or changes IPs, profiles,
  routes, instrument connections, outputs or runner state.
- `tests/test_v13_6_network_preflight.py` simulates the real topology,
  external dock, missing and saved host routes, invalid host and
  GUI worker structure.

**Important limitations:** The report is a snapshot. It cannot infer
whether a host route is persisted by non-NetworkManager mechanisms
(e.g., an external dispatcher), nor can it guarantee connectivity
after a reboot. No permanent OS setup is implemented or
hardware-tested. Next step: user runs read-only preflight on
Kubuntu and supplies its report, allowing a narrowly scoped proposal
for NetworkManager persistence. Any actual OS network changes
require explicit permission and a verified rollback plan.
The DSRemote `screen_thread.cpp line 783` fault remains deferred
on the backlog; it is not a prerequisite for PSU work.



## 2026-11-16 — DSRemote deferred; PSU v13.6 read-only route UX

**User direction:** DSRemote 0.46 connected with PSU GUI open, displayed
a running scope waveform, entered Wave Inspector, returned to main
screen, and later displayed `screen_thread.cpp line 783` and stopped
updating. Since the same error occurred with PSU GUI closed, and
separate Rigol RAW CH2/CH4 small-depth capture passed (6,000/6,000
each, 1,200-point blocks, decimation 1), **do not block PSU GUI
development on DSRemote debugging**. Record as deferred coexistence
backlog, not a proven PSU fault. The overlapping /16 routing issue
remains separate and must still be fixed persistently with
user-authorized OS changes.

**Implemented on PSU `dev`:** clarified empty PSU IPv4 field
behaviour (CSV address first, then discovery) in Network settings.
**Inspect routes** now supplements the subnet-overlap warning
with the effective Linux `ip -j -4 route get <PSU IPv4>` decision
(source address and interface) when an IP is entered and warns if
the selected adapter disagrees. This command is **read-only**;
it creates no socket, changes no IP, and applies no routes.
Added mocked regression tests of exact command, mismatch and
invalid address. **Source-implemented/offline-tested only until
latest GitHub CI run completes; not hardware/UI validated.**
No changes to PSU command sequencing, profile run, socket ownership,
pause/manual/resume, restoration or LOCAL.

**Next:** Run CI, launch updated GUI for a visual **Inspect routes**
check with the already-identified PSU `169.254.51.7` /
`enx0c3796303396`. User should not run Prepare adapter or make
persistent OS route changes without a reviewed design. Continue
persistent NetworkManager configuration planning; do not reopen
DSRemote investigation unless it blocks simultaneous lab use.



**Updated:** 2026-11-16  
**Project:** `FLRHW/PSU_control`  
**Active development branch:** `dev`  
**Stable release branch:** `main` (v13.5 merged from `dev`, PR #1, merge commit `7d5b3931404a9630c0343808e3ac7f695b289516`).  
**Functional milestone:** **v13.6 retained-socket fix, standalone Manual Control, and profile 10.csv hardware-validated** on 2026-11-16. Persistent automatic networking and other v13.6 features remain unvalidated. v13.5 hardware-accepted baseline remains on `main`.  
**Source baseline:** v13.6 retained-socket connection fix through `1c1b52454f29ebe418e5f912c0b2a936463cb7ef` (later docs-only commits; check current `dev` HEAD).

> This file is a compact start-of-session index. For full technical architecture, safety invariants and historic test evidence read [PROJECT_HANDOVER.md](PROJECT_HANDOVER.md). For milestones read [RELEASE_v13_5.md](RELEASE_v13_5.md) and previous release notes.

## Independent Rigol Ethernet waveform retrieval — PASS, limited size (2026-11-16)

User ran the separate Rigol capture application with DSRemote closed
and supplied the capture console:

```text
Instrument verified: RIGOL TECHNOLOGIES,DS1054Z,DS1ZA221303251,00.04.04.SP4
Network path: automatic system route
CH2: 576/576 points (100.0%)
CH2: wrote 2 of 576 acquired samples (decimate 500)
CH2: exported 2 rows, saved spacing 1 s (original spacing 0.002 s)
CH4: 856/856 points (100.0%)
CH4: wrote 2 of 856 acquired samples (decimate 500)
CH4: exported 2 rows, saved spacing 1 s (original spacing 0.002 s)
Saved: /mnt/Data/01_Engineering/01_Projects/301_Rigol_DS1054Z/Rigol_capture/captures/rigol_scope.csv
```

**Conclusion supported by observation:** Rigol could be identified
over Ethernet and all requested waveform samples for CH2 and CH4
were retrieved without a reported acquisition error, with automatic
system routing and the temporary correct Rigol /32 route in place.
Only two samples per channel were saved after **export decimation=500**.
This is a positive independent capture test but not proof of
sustained or high-volume transfer reliability. The earlier
DSRemote `screen_thread.cpp line 783` failure may be DSRemote-specific
or triggered by larger/continuous transfers; root cause unknown.
Next useful test: single capture with decimation 1 and a larger
memory depth if supported, plus check IP route at the time of
any DSRemote error. Do not conflate this separate capture tool
with PSU_control source or modify its code as part of PSU fixes.

## Rigol DSRemote connection recovered; waveform stream still fails (2026-11-16)

After the user re-added the Rigol-specific route, `ip route get`
selected `enp3s0f1` for `169.254.179.79`, while the PSU remained
routed via the D6000 `enx0c3796303396`. Rigol replied to all four
pings. The user then **successfully connected DSRemote** and observed
waveform data for several seconds, but it subsequently displayed
`An error occurred while reading screen data from device. File
screen_thread.cpp line 783`. The physical scope itself operates
normally; the user previously reproduced this error with the PSU GUI
closed. Therefore the **socket connection problem is resolved by
routing**, but the **independent DSRemote waveform-read failure remains
unresolved**. Neither a network packet-level diagnosis nor inspection
of DSRemote's exact source line has been completed. An older DSRemote
GitLab issue #5 documents the same text for a USB connection, which
does not establish the cause over LAN. Avoid attributing it to PSU GUI,
Qt rendering, cabling or firmware without evidence.

Recommended non-invasive follow-up: check `ip route get
169.254.179.79` immediately after the stream error, verify physical
oscilloscope acquisition continues, and try a separate single
screen/waveform capture through the already developed Rigol tool,
with DSRemote disconnected, to distinguish transport from the
DSRemote client. No PSU code or network routes were altered by
this investigation.

## Confirmed Linux route-selection failure (2026-11-16)

User provided real workstation command outputs with both instruments powered on:

```text
ip route get 169.254.179.79
169.254.179.79 dev enx0c3796303396 src 169.254.51.8
ip route get 169.254.51.7
169.254.51.7 dev enx0c3796303396 src 169.254.51.8
ip -4 route
169.254.0.0/16 dev enx0c3796303396 proto kernel scope link src 169.254.51.8
169.254.0.0/16 dev enp3s0f1 proto kernel scope link src 169.254.10.1 metric 100
```

NetworkManager shows `enp3s0f1` **Wired connection 2** with
`169.254.10.1/16`, while D6000 `enx0c3796303396` remains
**connected (externally)** with temporary `169.254.51.8/16`.
Wi-Fi remains connected via `wlp4s0` to `192.168.0.1`.
**Root cause of DSRemote initial connection failure confirmed:** the
Rigol IP `169.254.179.79` was routed to the D6000 (PSU) adapter
rather than the built-in Rigol adapter. The earlier `/32` route
exception had disappeared after network/link state changes. This
explains failed socket establishment to Rigol, not necessarily the
separate intermittent DSRemote screen_thread.cpp waveform-read error.

**User confirmed executing the temporary remedy successfully:**
`sudo ip route replace 169.254.179.79/32 dev enp3s0f1 src 169.254.10.1`.
Subsequent `ip route get` selected built-in `enp3s0f1` for Rigol
`169.254.179.79` (source `169.254.10.1`) and dock
`enx0c3796303396` for PSU `169.254.51.7` (source `169.254.51.8`).
Rigol answered **4/4 pings with 0% loss**, mean **0.273 ms**
(min 0.202 ms; max 0.349 ms). **DSRemote application reconnection is
not yet confirmed** by the user; ping alone tests IP reachability,
not DSRemote waveform transfer or scope service health.
No OS network configuration was changed by the assistant. Next
work is persistent, interface-specific routing that does not disrupt
other existing connections; any mutation requires user approval.

## Powered-off versus powered-on Rigol route check (2026-11-16)

- **User GUI validation:** HOLD preview text absent and compact toolbar
  accepted after syncing latest `dev`.
- **Physical observation:** With the Rigol powered OFF, pressing
  **Inspect routes** displayed "No overlapping IPv4 network routes
  found." The user then supplied an updated screenshot after powering
  the Rigol ON, indicating that the route audit must be interpreted
  with link/device state. The two direct Ethernet networks have
  previously produced overlapping `169.254.0.0/16` routes and
  misrouted traffic; the temporary explicit Rigol host route was
  successful. **No persistent fix or reboot verification yet.**
- **Code safety improvement (offline tested):** `setup_ethernet_link_local`
  now refuses to create a new link-local profile if an existing
  different interface has a conflicting active IPv4 network route.
  `network_route_summary` now explains that a no-overlap report is
  only a snapshot and recommends checking with all instruments
  attached. This may also refuse legitimate multi-instrument setups
  until an explicitly reviewed persistent routing solution exists;
  this conservative refusal is intentional.
- **CI PASS:** [run #43960100687](https://github.com/FLRHW/PSU_control/actions/runs/43960100687),
  code commit `51da112222721764480592a9c0cb2af671929a0d`:
  **134 tests run; 132 passed, 2 skipped**, no failures.
- **Next:** no OS changes or reboot yet. Require an explicit
  user-authorised persistent design protecting Rigol, dock and Wi-Fi;
  verify both powered-up routes and connection tests following
  configuration. `main` remains v13.5.

## Current v13.6 increment — user-requested layout and route audit (2026-11-16)

- **Implemented on `dev`:** Removed all Profile Runner
  `CHx initially HOLD`, `CHx HOLD: initial output state retained`
  and `CHx OFF throughout` preview messages and the toolbar
  info label. The user explicitly requested that the HOLD text not
  appear anywhere in the GUI. **No CSV, output-control, snapshot,
  validation or restoration semantics changed**; preview failures
  still appear in console/status.
- **Implemented on `dev`:** moved **Network settings…** immediately
  right of the Profile duration field, removing the separate
  left-column row to reclaim vertical graph space.
- **Implemented on `dev`:** **Inspect routes** button in the
  Network settings dialog, calling a strictly read-only
  `ip -j -4 route show table main` audit. Reports overlapping
  non-host IPv4 prefixes across different devices, and ignores
  /32 host-route exceptions. No `nmcli`, `sudo` or route writes.
- **Offline tests added/updated** in `tests/test_v13_6_network_dialog.py`
  and `tests/test_v13_6_network_setup.py`.
- **Hardware status:** current user workstation has NOT yet
  run this new layout or route-audit increment. Previously verified
  Test connection, Manual Control and 10.csv run remain the last
  physical tests. Persistent NetworkManager setup, reboot survival
  and overlap-safe configuration remain **not implemented/verified**.
- **User next step once CI is green:** `git switch dev; git pull --ff-only
  origin dev; python3 scripts/cpx400dp_gui.py`. Confirm HOLD text is
  absent and **Network settings…** is beside Profile duration. In
  that dialog, click **Inspect routes** (read-only) and send the
  message shown. Do not run `Prepare adapter…`, change routes or
  reboot until persistence is safely designed.
- **Engineering workflow preference:** user explicitly authorised
  proceeding with subsequent offline coding, regression checks and
  documentation rather than stopping after every small increment
  for another "go ahead". Request user input only for actual
  instrument tests, OS networking authorisation and decisions that
  require hardware/user approval.

## Network settings dialog hardware acceptance — PASS (2026-11-16)

- User pulled the PyQt5 `QDialog` import correction; the GUI launched
  successfully and the new `Network settings…` dialog looked correct.
- **Live physical test passed:** with PSU IPv4 field initially blank,
  pressing **Test connection** discovered the Thurlby Thandar CPX400DP,
  serial `446696`, firmware `2.00-4.06`, at `169.254.51.7` via
  Dell D6000 interface `enx0c3796303396`. The GUI populated the
  verified IP automatically and displayed `Test socket closed;
  profile not started`. The dialog's full IP and interface were
  readable and the layout was user-approved.
- **Scope:** network dialog opening, visibility, automatic discovery,
  auto-filled verified address, and read-only temporary TCP test are
  **hardware/UI validated**. Adapter preparation/NetworkManager
  persistence, post-reboot operation and competing 169.254/16 routes
  are **not validated**. No new profile run was necessary because
  the prior retained-socket 10.csv hardware test passed.
- **Next priority:** safe persistent configuration for separate direct
  Ethernet instruments, preserving both Rigol and PSU connectivity.
  Consider replacing the blank IP placeholder with an explicit
  `Automatic discovery` indication. Do not change network routes
  without explicit approval.

## Network dialog PyQt5 startup regression — fixed (2026-11-16)

- **Hardware/UI failure reported:** After syncing `dev` to commit
  `8c40862` the user launched `python3 scripts/cpx400dp_gui.py`;
  the GUI aborted during `Window.__init__` at `QDialog(self)` with
  `NameError: name 'QDialog' is not defined`. The PySide6 QtWidgets
  branch included `QDialog`, but the fallback **PyQt5** branch on the
  user's Kubuntu system omitted it. The previous offline GUI tests had
  checked only structure, not both import branches.
- **Fixed on `dev`:** add `QDialog` to the PyQt5 QtWidgets import
  and add an AST regression test verifying `QDialog` is imported in
  **both PySide6 and PyQt5**. This changes no connection logic.
  Source/test commits: `44baae28` / `ea2c0041`.
- **CI PASS:** [run #43926670863](https://github.com/FLRHW/PSU_control/actions/runs/43926670863),
  **128 run, 126 passed, 2 skipped, 0 failures**.
  **GUI relaunch on the real Kubuntu workstation is pending**; CI
  does not verify visual Qt rendering.
- **Rigol independent fault clarified:** The user confirms the DS1054Z's
  own physical screen/acquisition behaves normally while DSRemote
  reports `An error occurred while reading screen data from device.
  File screen_thread.cpp line 783`, including with the PSU GUI closed.
  This focuses further investigation on DSRemote's capture/transport/
  rendering path rather than oscilloscope acquisition hardware, but
  does not distinguish network transfer from DSRemote software handling.
  Do not assume CPX400DP GUI interaction is the root cause.

## Network settings dialog + DSRemote status (2026-11-16)

- **Implemented on dev, offline-tested:** Profile Runner now shows one
  **Network settings…** button instead of cramped inline network controls.
  A separate nonmodal dialog holds full-width IP and interface widgets,
  read-only Test connection, opt-in Prepare adapter, and diagnostic status.
  Opening the dialog alone does **not** probe the network or configure
  an adapter. The existing validated discovery and single-socket logic
  and operation ownership guards are retained. New
  `tests/test_v13_6_network_dialog.py` checks layout and safety.
- **CI PASS:** GitHub Actions
  [#43925537774](https://github.com/FLRHW/PSU_control/actions/runs/43925537774)
  for code/test commit `c2b3d6e688c2e553df7882d66ee4dd98fad57bf1`
  completed successfully. No physical/visual acceptance of the new
  dialog has yet been performed.
- **User's independent Rigol finding:** DSRemote suffered
  corrupted/non-updating waveform display after horizontal-scale
  changes, initially with PSU GUI open. Closing PSU GUI and reconnecting
  DSRemote initially seemed to fix it, but it **recurred with PSU GUI
  fully closed**. This disproves the claim that the PSU GUI must be
  open to reproduce the DSRemote fault; root cause still unverified.
  Treat Rigol investigation as separate from CPX400DP control changes.
- **Next:** sync `dev`, inspect the Network settings dialog for readable
  values; test its read-only identification only when no PSU session is
  active. No new PSU hardware profile is needed for the layout revision.
  Separately check Rigol front-panel acquisition vs DSRemote display
  during horizontal-scale changes and verify direct scope networking if
  necessary. NetworkManager persistence and safe overlapping-route
  management remain unimplemented and in `docs/BACKLOG.md`.

## Hardware validation — simultaneous Rigol/PSU operation (2026-11-16)

**User-confirmed hardware results:** With Rigol DSRemote open and updating,
the PSU **Test connection** identified `THURLBY THANDAR, CPX400DP,
446696, 2.00-4.06` at `169.254.51.7:9221` via Dell D6000
`enx0c3796303396`; DSRemote continued updating. Standalone
**Manual Control** connected, displayed both channels' programmed
and measured values, and disconnected successfully (user confirmed).
The user then ran `profiles/10.csv` with CH1 and CH2 selected,
50 ms steps, 250 ms readbacks, 0 s initial and 2 s final ramp.
**Result: run completed, exit code 0**.

**Runner evidence** (user-supplied Run output, run ID
`20261116_174633_754482`):
- `[PSU DISCOVERED]`, `[PAUSE CONTROL READY]`,
  `[SNAPSHOT VERIFIED]` (two matching programmed-state reads);
  initial CH1 5.000 V / 1.500 A / ON and CH2 3.000 V / 4.000 A / ON.
- 401 scheduled main-profile slots; 441 setpoint groups;
  1204 instructions; 564 unchanged settings suppressed;
  maximum scheduling lateness 0.905 ms.
- 178 successful readbacks, **0 failed**; one expected settling
  readback, zero unexplained high readbacks, no output-health warnings
  and no sustained-fault abort.
- Both channels' **programmed final state VERIFIED**; post-restoration
  physical output **MATCHED (sampled, not continuous proof)**;
  `LOCAL: SENT`, `Run status: COMPLETED — cleanup verified`;
  HTML report generated.
- User reports **DSRemote also appears to work normally**.
  This verifies coexistence for this particular setup/run, not
  uninterrupted long-term reliability or post-reboot routing.
- Logs on user's workstation:
  `reports/10_console_20261116_174633_754482.log`,
  `reports/10_measurements_20261116_174633_754482.csv`,
  `reports/10_report_20261116_174633_754482.html`.
  Only Run output was supplied, not full CSV/report bytes.

**Validation classification:** Actual physical PSU test PASSED for
retained verified socket, initial-state snapshot, standalone manual
readout/disconnect, 20 s profile, restoration and LOCAL. The software's
50 ms scheduling and measured sub-1 ms lateness are not physical
SCPI processing time guarantees. User-confirmed DSRemote coexistence
is limited to this session. NetworkManager persistent setup, restart
survival, external-connection migration, multiple-PSU and VXI-11
paths remain pending.

**Next:** Do not change networking while currently working. Prioritise
a user-friendly persistent configuration that preserves the Rigol
host route and avoids two competing 169.254/16 default routes; request
explicit OS-configuration approval. Controlled reboot test only once
persistent setup is ready. Keep other work in `docs/BACKLOG.md`.

## Current increment — verified TCP session reuse (2026-11-16)

- **User hardware finding:** `Test connection` identified CPX400DP
  serial `446696` at `169.254.51.7` via Dell D6000
  (`enx0c3796303396`), but the runner subsequently printed
  `[PSU DISCOVERED]` followed immediately by
  `[Errno 111] Connection refused`. No initial snapshot or
  output commands occurred; generic GUI restoration warning was misleading.
- **Implemented on `dev`:** `cpx400dp_discovery.py` retains the exact
  successfully `*IDN?`-verified TCP socket and gives it to the runner or
  ManualWorker. It closes all nonselected and ambiguous/failed candidate
  sockets. The GUI's standalone **Test connection** still uses a
  temporary socket and closes it immediately. Runner snapshot/restore
  and `LOCAL`-last have not been weakened.
- **Implemented on `dev`:** runner emits
  `[CONNECTION NOT ESTABLISHED]` on pre-snapshot connection failure.
  GUI reports **PSU connection failed — profile not started**, not
  `restoration requires attention`, when no control session was
  established. No profile commands are sent in this path.
- **Offline CI PASS:** GitHub Actions
  [#43920224405](https://github.com/FLRHW/PSU_control/actions/runs/43920224405)
  on code commit `1c1b52454f29ebe418e5f912c0b2a936463cb7ef`:
  **123 tests run, 121 passed, 2 skipped, zero errors/failures**.
  Five new offline socket-lifecycle tests verify session reuse, read-only
  test closure and ambiguous-device cleanup. Documentation-only commits
  follow. **Retained connection has not yet been tested on the real PSU.**
- **Rigol networking:** When D6000 `169.254.51.8/16` was added, Linux
  routed the Rigol `169.254.179.79` to the wrong adapter. The user
  temporarily installed a `/32` host route via `enp3s0f1`; both
  current route lookups then matched the intended physical devices, and
  the Rigol answered four pings. The user additionally saw DSRemote's
  waveform rendering fail while the PSU GUI was open, then recover
  after GUI closure. This is an **unresolved correlation**, not proof
  of ongoing network scanning or software interference.
- **Next hardware task:** sync `dev` and perform a controlled
  connection/snapshot/profile test while preserving the corrected
  temporary routes. Confirm final state and `LOCAL` on the physical
  PSU and whether Rigol DSRemote remains operational. The user performs
  hardware checks; the assistant changes and documents repository code.
  No reboot or further `sudo nmcli` actions until the networking
  regression is characterised.
- **Deferred:** persistent NetworkManager configuration, overlapping
  subnet protection, long-duration report/log scalability, and
  regulation-mode indicator physical validation remain in
  [BACKLOG.md](BACKLOG.md). Keep `main` on stable v13.5.

## Active v13.6 priority — PSU connection UX (2026-11-16)

**User hardware:** Rigol DS1054Z direct to `enp3s0f1` on the
workstation; CPX400DP via Dell D6000 `enx0c3796303396`.
Two independent `169.254.0.0/16` networks previously caused incorrect
source/route selection. The dock interface was UP without IPv4; the user
added temporary `169.254.51.8/16`. Read-only GUI connection discovery has now succeeded with this temporary
IP; NetworkManager setup and reboot persistence remain untested.

- **Implemented on dev:** `scripts/cpx400dp_network_setup.py` physical
  Ethernet inspection (including no-IPv4 dock links), read-only diagnostic
  outcomes, and an explicit-confirmation NetworkManager/Polkit one-time
  link-local profile operation. Refuses Wi-Fi, virtual interfaces, missing
  carrier, active NetworkManager profiles and adapters that already have IPv4.
- **Implemented on dev:** `cpx400dp_discovery.py` uses both
  `SO_BINDTODEVICE` and matching IPv4 source binding for link-local TCP
  probes, plus an explicitly selected multicast source for mDNS.
  Existing cache/ARP/mDNS/`*IDN?` verification is retained.
- **Implemented on dev:** Profile Runner **Test connection** (temporary
  read-only socket), optional **Prepare adapter…** after explicit approval,
  clear status/ambiguity messages; checks suppressed during profile/manual
  ownership; successful identification sets the selected host/interface.
  CSV chooser now saves last-used directory, initially the `profiles/`
  folder.
- **Offline CI PASS:** [run #43914927927](https://github.com/FLRHW/PSU_control/actions/runs/43914927927)
  at code commit `a43fb655076a41b99c52d1290c50176c151c8ecd`:
  **118 tests run; 116 passed, 2 skipped, no failures**. Existing safety
  tests remain green; new tests cover the unconfigured dock, NetworkManager
  safety checks, source binding, duplicate identity and GUI controls.
  Documentation-only commits follow; no source/test changes.
- **HARDWARE IDENTIFICATION PASS (2026-11-16):** User launched the GUI,
  selected **Test connection**, and confirmed a successful live `*IDN?`
  response: `THURLBY THANDAR, CPX400DP, 446696, 2.00-4.06` at
  `169.254.51.7:9221` via `enx0c3796303396` (D6000). GUI states
  **Test socket closed; profile not started**. No profile/manual-control
  operation or PSU state change was performed by the test. Terminal also
  showed a harmless Qt Wayland window activation warning.
  **Still unvalidated:** one-time NetworkManager preparation, IP persistence
  across reboot, and full v13.6 runner/Manual Control hardware behaviour.
- **Next action for user:** check whether D6000 adapter's temporary
  `169.254.51.8/16` address is now managed persistently by NetworkManager;
  test or configure one-time persistent link-local setup when safe and verify
  read-only discovery after a reboot. Do not modify the PSU's network settings
  or start an energised run solely to diagnose connectivity.
- **Backlog retained:** [BACKLOG.md](BACKLOG.md) tracks truly bounded-memory
  reporting, longer-duration logging/zoom/recovery, hardware CV/CC
  last-event validation, optional VXI-11 discovery and network error recovery.
  `main` stays on released v13.5 pending explicit permission to merge.

## v13.6 development — current increment (2026-11-15)

- **Implemented (dev, not yet hardware-tested):** `scripts/cpx400dp_run_enhanced.py` now streams scheduled ticks through an iterator instead of allocating all regular ticks at once; `validate_schedule()` checks potentially short gaps around user keyframes and phase endings without walking the full time grid. The completed-tick counter is incremental.
- **Offline tests added:** `tests/test_v13_6_long_schedule.py` tests short-profile compatibility, sorted/deduplicated keyframes, 1,000-hour duration with 50 ms minimum interval (without executing 72 million ticks), rejection of a 25 ms-offset keyframe, final phase ending too close to regular tick and ramp gap.
- **Offline regression PASS:** GitHub Actions run [#43738935671](https://github.com/FLRHW/PSU_control/actions/runs/43738935671) completed successfully on code/test commit `d7acf2c3abfbfbe508afdbbe35cc96af65ea27c5`: **101 tests run, 99 passed, 2 skipped, 0 failures/errors**, 9.218 s. All six new long-schedule tests passed; two existing skips require uploaded hardware recordings. Later documentation-only commits do not alter this code/test baseline. No PSU hardware test of v13.6 has been performed.
- **Implemented (dev, offline-tested as of commit `16054d1`):** standalone Manual Control and paused-profile Manual Control now show the last unambiguous regulation-mode event (`CV`, `CC`, `UNREG`, or `FAULT`) or `UNKNOWN`; a label explicitly says **last event** rather than implying live mode. The official CPX400DP manual defines `LSR1?`/`LSR2?` as **read-and-clear** event registers: bit 0 entering CV, bit 1 entering CC, bit 4 entering UNREG, bits 2/3/6 protective trip/OCP/OVP. Multiple contradictory event bits yield unknown. A zero read retains a previously seen unambiguous mode while enabled; OFF resets it. Standalone worker uses its own existing TCP connection; paused-profile reads are routed exclusively through the runner's socket. Nonzero paused read-and-clear LSR replies are persisted as `limit_event_sample` in the measurements CSV so diagnostics are not silently discarded. **This is historical event information, not independently verified live mode, and no v13.6 instrument tests have been run.**
- **Implemented (dev, offline-tested):** `cpx400dp_preview.py` adapts its graph and enable-state strip time units (seconds/minutes/hours/days), keeping its 1,201-point regular-preview cap plus user keyframes. `cpx400dp_report.py` adapts time units, preserves subsecond timestamp tick-label precision even near 1,000 hours, avoids large JS `Math.max(...arrays)` calls, and renders visible series using per-pixel first/last/min/max retention instead of global fixed-stride selection. Source tests plus generated HTML and preview smoke tests are included.
- **Latest offline regression PASS:** GitHub Actions run [#43746631345](https://github.com/FLRHW/PSU_control/actions/runs/43746631345) on code commit `16054d124f864b634968bfd44a11331672ba72cf`: **110 tests, 108 passed, 2 skipped, 0 failed**; later README/documentation updates contain no source or test changes. No v13.6 hardware tests performed.
- **Still planned / unresolved:** true bounded-memory CSV log processing, storage/retention and high-density graph zoom on very large 1,000-hour histories; recovery from disconnect/reboot and multi-day reliability. CPX400DP LSR last-event indication requires physical verification against front-panel CC/CV transitions, including ambiguous events; its read-and-clear nature prevents asserting continuous live mode. Additional stress and usability testing required before v13.6 release.
- The 1,000-hour/50 ms test is a **synthetic bounded-time scheduler check**, not a 41-day run, throughput guarantee or evidence of unattended reliability. Maintain safe failure/cleanup behaviour.

## Currently implemented in dev

- Qt Profile Runner and Manual Control tabs, configurable CSV-driven stepped/linear profiles, offline preview and interactive HTML measurement reports.
- Ethernet PSU discovery and interface selection, verified programmed-state snapshots, command/readback parsing, output-health monitoring and cleanup.
- Pause/manual/resume via runner-owned TCP socket and local IPC; pause-point restoration and verification before resuming.
- Manual output state shown prominently as green ON, red OFF or grey unknown; Enable/Disable actions unavailable when redundant or state unknown.
- No confirmation popup for output enabling in standalone or paused-profile Manual Control, and none on Resume.
- Two-decimal manual V/A display without rounding internal communication/log values.

## Branch/version reconciliation

- The release PR [#1](https://github.com/FLRHW/PSU_control/pull/1) was merged on 2026-11-15, merge commit `7d5b393`. v13.5 is now on `main`. The `v13.5` annotated tag creation was delegated to the user and was not independently confirmed when v13.6 began.
- `dev` remains the active development branch. First v13.6 code commit `5a992c9`; new offline tests `d7acf2c`.


- Historical: `main` originally held a **v13.3** import; it now contains the merged v13.5 release.
- `dev` carries released v13.4/v13.5 code and **new v13.6 scheduler changes**, plus documentation.
- `docs/RELEASE_v13_4.md` describes behaviour **at v13.4**, including the then-retained standalone enable confirmation. It is historical and superseded on `dev` by v13.5; do not rewrite historical behaviour.
- The old README title incorrectly implied the entire `dev` tree was still v13.3; README and v13.5 notes were updated to distinguish current development from stable/import baseline.
- No verified version tag, actual instrument test or full current test pass is inferred from these labels.

## Offline testing automation (2026-11-15)

- New `.github/workflows/offline-tests.yml` on `dev` runs Python compilation and the entire `unittest discover` suite on GitHub Actions on pushes/PRs, with headless Qt and Matplotlib dependencies. No real PSU, instrument network access, or large stored artifacts are required.
- Workflow added in commit `06dbdd3fbfc40e280da5cfd998c8c1de9b3a5921`; workflow result **independently verified**: [GitHub Actions run #43734073069](https://github.com/FLRHW/PSU_control/actions/runs/43734073069), commit `69d0e0ccc1f6aee86f58a948e144862afcb94ee2`, completed with `conclusion=success` on 2026-11-15. `unittest` reported **95 tests, 0 failures/errors, 2 skipped, 9.756 s**. The skips were `test_actual_hardware_log_context` (no uploaded hardware recording) and `test_report_has_offline_zoom_and_cursors` (uploaded HW data not mounted). Compilation and the full available offline suite succeeded.
- Policy: assistant handles code-only/offline regression, simulation and CI; user handles physical-CPX400DP/oscilloscope/load validation only.

## Latest work (2026-11-15)

- Reviewed key source files (`cpx400dp_gui.py`, `cpx400dp_gui_core.py`, `cpx400dp_run_enhanced.py`, `cpx400dp_manual.py`, `cpx400dp_discovery.py`, `cpx400dp_preview.py`, `cpx400dp_report.py`) against the partial exported prior conversation.
- Committed `docs/PROJECT_HANDOVER.md` on `dev` at `a118b9e`.
- Added v13.5 development notes and reconciled README version/status.
- Established this `SESSION_STATE.md`.
- **No source or test code changed, no automated tests executed, no physical PSU tests performed during this documentation session.**

## v13.5 staged physical validation (reported by user, 2026-11-15)

- **Stage 1 — PASS (user-reported):** Completed the full standalone Manual Control checklist: connection and programmed readback, no confirmation when enabling output, appropriate enabled/disabled buttons and colour indicators, disabling output, voltage/current-limit commands and readback, disconnect with settings preserved and LOCAL mode. No per-step logs or recordings supplied; this is **user-reported hardware validation**, not independently reviewed instrument telemetry.
- **Stage 2 — PASS (user-reported and independently log-reviewed, 2026-11-15):** User confirmed the ten-item hardware checklist; subsequently provided `18.csv`, `18_console_20261115_162059_692166.log`, `18_measurements_20261115_162059_692166.csv`, and `18_report_20261115_162059_692166.html`. Review confirmed a 150 s profile, 50 ms scheduling, 250 ms readbacks, 2 s final ramp, 54.372 s pause beginning at profile time 11.200 s, and verified paused-manual CH1 voltage 8.900 V, CH1 OFF/ON, CH2 ON. The runner verified reversion to the saved pause-point CH1 8.000 V/1.300 A/ON and CH2 3.000 V/0.500 A/OFF before `[RESUMED]`; profile time was frozen during the pause. On normal completion, original CH1 7.800 V/0.900 A/ON and CH2 2.100 V/0.200 A/ON were programmed-state VERIFIED and post-restoration physical readbacks MATCHED (sampled only). 1,652 readbacks succeeded, zero failed; 0 output-health warnings, 0 unexplained high readbacks, 1 expected settling transient; maximum lateness 0.946 ms; LOCAL sent last; GUI runner exit code 0. **Log findings support normal-completion restoration; Stage 3 interruption/restoration still pending.**
- **Stage 3 Test A — PASS for interrupted-run programmed restoration (log-reviewed, 2026-11-15):** User uploaded `10(2).csv`, `10_console_20261115_163034_913795.log`, `10_measurements_20261115_163034_913795.csv`, `10_preview(1).html` and `10_report_20261115_163034_913795.html`. Linear, two-channel profile configured for 20 s with 50 ms setpoint slots and 250 ms readbacks, stopped via GUI SIGINT at **7.661330 s** of profile execution. Initial snapshot CH1 **1.000 V / 2.000 A / ON**, CH2 **3.000 V / 4.000 A / OFF**. `final_state_sent` occurred for both, followed by `final_state_verified` for CH1 at 7.819347 s (two query attempts) and CH2 at 7.833223 s (one query attempt). CH1 physical advisory sample **1.467 V vs 1.000 V setpoint**, classified MATCHED under the software's **0.5 V or 5%** tolerance, but is a transient-sized 0.467 V difference, *not proof of settled output*. CH2 physical check N/A because OFF. Diagnostics `*STB?`, `*ESR?`, `EER?`, `QER?` zero; 62 successful readbacks/0 failed, maximum lateness 0.849 ms, no output-health warnings. `local_sent` recorded at 7.872354 s; final `command_summary` is a log-only event, not a further PSU command. Console reports `INTERRUPTED — cleanup verified` and runner **exit code 130** (expected for intentional SIGINT), with generated interrupted HTML report. No independent observation of front-panel LOCAL status was supplied.
- **Stage 3 Test B — PASS for paused-interruption programmed restoration (independently log-reviewed, 2026-11-15):** Files provided: `14(1).csv`, `14_console_20261115_163816_660976.log`, `14_measurements_20261115_163816_660976.csv`, `14_preview(1).html`, `14_report_20261115_163816_660976.html`. The two-channel 26 s linear profile ran with 50 ms scheduler intervals and 250 ms readbacks, then paused at profile time **7.200 s**. Three paused-manual output commands were individually readback verified: **CH1 OFF**, **CH2 OFF**, **CH2 ON**. Stop/SIGINT occurred at wall-clock elapsed **21.257 s** with **no resume event**. On cleanup, the original pre-run settings were restored: CH1 **1.000 V / 2.000 A / ON**, CH2 **3.000 V / 4.000 A / OFF**. Both `final_state_verified` entries succeeded on first query attempt. CH1 sampled physical output was **0.987 V** (1.000 V setpoint), classified MATCHED; CH2 physical output check N/A because OFF. **170 successful readbacks, 0 failed, maximum recorded lateness 0.598 ms, 0 output-health warnings**; raw final status queries `*STB?`, `*ESR?`, `EER?`, `QER?` were zero. `local_sent` recorded as the last PSU command; final outcome **INTERRUPTED — cleanup verified**, runner exit code **130** expected for SIGINT. Report correctly labels INTERRUPTED. The log does **not independently establish** front-panel LOCAL unlock or GUI idle/new-run readiness; these remain user-observation checks.
- Do not merge to `main` solely on Stage 1/Stage 2 user reports; review Stage 3 and evidence, and retain CI validation for the eventual source commit.

## Final Stage 3B hardware observations (user-confirmed, 2026-11-15)

- Following Test B, user explicitly confirmed the **physical CPX400DP front panel returned to LOCAL** and the **GUI returned to its idle state**. These are direct user observations, not deductions from the `local_sent` log.
- Taken with offline CI (95 tests, 2 skips due to missing recordings), Stage 1 checklist, and independently reviewed Stage 2 / Stage 3A / Stage 3B logs, the planned **v13.5 functional acceptance tests are complete**.
- No `main` merge, release tag, or code change is authorized by this observation alone. Before release: reconcile `dev` vs `main`, ensure currently tested code is unchanged since its CI pass (documentation-only commits have occurred), and seek explicit approval for merge/tag.
- Important limits: no evidence for multi-day unattended reliability; 1000-hour profile handling and CV/CC indications remain **future requirements**, not features of v13.5.

## Next-revision enhancement request (user observation, 2026-11-15)

- **Display per-channel CV / CC regulation status in the Manual Control tab**, including standalone Manual Control and, if practical, paused-profile Manual Control. Current UI shows programmed state, measured voltage/current, and ON/OFF, but not CV/CC.
- Do **not** infer the mode merely from a comparison between measured voltage and current limit. First consult the CPX400DP programming manual to identify an authoritative per-channel status query/register and the actual CV/CC bit semantics; `LSR1?` / `LSR2?` are currently collected as raw diagnostic queries by the runner, but their bit fields have not been validated here.
- Display **CV**, **CC**, or **Unknown / unavailable** where appropriate (including OFF or ambiguous readbacks); do not misrepresent unknown as CV.
- Preserve the instrument's single-socket ownership: standalone manual worker should query on its existing socket; paused-profile manual control must route through the active runner, not open a competing connection.
- Keep status queries non-disruptive, check whether any status registers are clear-on-read, avoid degrading 50 ms profile scheduling or interfering with existing diagnostics. Add mocked protocol, state/UI, and no-extra-socket offline tests before any hardware trial.
- **Deferred until the next software revision.** This entry changes documentation only; Stage 2 and Stage 3 v13.5 testing remain on the current unchanged code.

## Next-revision requirement — long-duration time axis and 50 ms resolution (2026-11-15)

**User request:** Support profiles lasting **at least 1,000 hours (3,600,000 seconds)**, while retaining the option to specify **50 ms (0.05 s)** setpoint updates and closely spaced CSV keyframes. This applies to profile validation/execution and to useful time axes in preview and post-run reports, not just the labels in a graph.

**Engineering implications identified from the currently inspected source:**

- `cpx400dp_run_enhanced.schedule_for()` currently materialises a full list of time slots. At 1,000 hours with a 50 ms period, that is **72,000,000 slots**, so list-based schedule construction/validation/execution is not acceptable. Replace with a lazy/streamed or otherwise bounded-memory schedule, including irregular keyframes and phase boundaries; preserve the 50 ms minimum-spacing rule and deterministic monotonic deadlines.
- `cpx400dp_report.py` loads the entire measurement CSV into a list and embeds all trace arrays in its HTML/JS; its graph uses array-spread `Math.max(...allTimes)` and constructs large arrays. These patterns must be reworked for long histories. Use streaming aggregation and scalable rendering/downsampling (preserve extrema, transitions, short excursions and ability to inspect zoomed windows); document tradeoffs for enormous recordings.
- `cpx400dp_preview.py` already limits regularly sampled preview points to 1,201 but includes all keyframes: ensure long-duration and dense-keyframe files remain usable with bounded rendering.
- Avoid treating **maximum profile duration** and **minimum scheduling interval** as coupled constraints. Accept at least 1,000 h even when the interval is 0.05 s; do not generate 72 million CSV rows or plotting vertices merely to represent a long ramp. Preserve detailed timing precision in the model/log even if the chart auto-selects hours/days as human-readable units.
- Support intelligent x-axis units (seconds/minutes/hours/days), zoom and pan down to 50 ms-scale regions, with numerically correct cursor/elapsed measurements across long durations. Large timestamp arithmetic, progress percentage, durations and pause/resume accounting require regression tests.
- A single test setup of 1,000 h at 50 ms would create huge command traffic/logs and run for more than 41 days. **Supporting the profile is not a guarantee of uninterrupted physical PSU communication, timing accuracy or safe unattended operation over that period.** Treat storage, log rotation/streaming, system sleep/reboot, recovery, and network failures as distinct documented concerns.
- Add tests for a synthetic 1,000 h profile with 50 ms interval that complete quickly **without iterating every tick**, plus targeted checks for schedule gaps at irregular keyframes, late-stage timestamps, zoom/cursor accuracy and bounded-memory report processing.

**Status:** Requirement queued for a future software revision alongside per-channel CV/CC indicators. Do **not** modify the ongoing v13.5 Stage 2/3 hardware-test baseline to implement this feature.

## Known validation evidence and gaps

- Historical v13.4 session: reported **94 offline tests passed**; hardware and GUI visual validation were outstanding at that point.
- Historical v13.5 session: reported **six focused handler checks passed**, but **full regression suite not run**.
- Older 50 ms scheduling runs and Ctrl+C restoration investigations are covered by the handover; they are evidence for past versions, not a substitute for v13.5 validation.
- Current `dev` offline suite **passed at commit `69d0e0c`** (95 tests, 2 skipped for unavailable hardware recordings); future source changes require a fresh CI result. Hardware Stages 1 and 2 passed (Stage 2 log-reviewed), and both Stage 3 Test A and Test B **passed log-based restoration checks**. Physical front-panel LOCAL confirmation and GUI idle recovery **confirmed by user after Test B**; no merge to `main` yet. Verify local working tree matches remote branch before hardware testing.
- Software is not a fail-safe protection mechanism; loss of LAN can prevent restoration.

## Next actions, in order

1. Assistant: verify `dev` CI after connection fix (source commit
   `1c1b524`, 123 tests, 2 skipped). Do not change `main`.
2. User: sync `dev`; verify current PSU front-panel settings, then
   perform read-only **Test connection** with Rigol DSRemote open.
3. User: test a controlled low-energy PSU profile with a safe load or
   outputs disabled, and confirm the initial snapshot, the runner's
   final verification and the PSU's local/front-panel state.
4. Record the actual hardware observations and investigate DSRemote
   problems separately against the known-correct temporary routes.
5. Return to NetworkManager persistence/overlapping routes after
   transport and coexistence are validated. Other features in
   [BACKLOG.md](BACKLOG.md).

## Start-of-next-chat prompt

> Inspect `FLRHW/PSU_control` branch `dev`, starting with `docs/SESSION_STATE.md` and `docs/PROJECT_HANDOVER.md`. Verify current HEAD and implementation before editing. Keep `main` unchanged unless explicitly requested. Preserve single instrument-socket ownership, pause-point verification, final restoration and LOCAL-last. After work, update session state with exact tests performed and current limitations.
