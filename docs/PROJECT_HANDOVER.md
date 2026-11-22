# CPX400DP controller — engineering handover

## 2026-11-22 — Post-fix 15-ohm GUI hardware validation (17:56 run)

User provided eight fresh screenshots of the 90-second supervised
`hardware_demo_90s_15ohm_REQUIRES_LOAD.csv` test after the CV/CC
display-cadence fix. The images show:
- Magenta **NOW** marker at ~7 s (~7%), ~26 s (~28%),
  ~44 s (~47%), and finally at the 90 s endpoint (~100%).
  Marker visibly advances along the step-profile preview,
  including during the low-current interval. A separate explicit
  screenshot proving it held *stationary throughout* pause is
  not supplied in this set.
- CH1 **CV likely (V/I estimate)** at 3.99 V / 0.27 A around
  26 s, and **CC likely (V/I estimate)** at 2.26 V / 0.15 A
  around 44 s. These are physically consistent with the
  15-ohm resistor and the CSV's 6 V / 0.15 A current-limit
  interval (nominal 2.25 V under CC). This constitutes visual
  hardware acceptance of the **post-fix** conservative
  estimation display, not an independently queried hardware
  CV/CC operating-mode register.
- Paused-profile Manual Control shows CH1 measured 9.99 V /
  0.67 A, programmed 10.00 V / 2.00 A, output ON and
  `CV (last event)`; these are user-commanded temporary
  manual values, not the example CSV's 8 V / 0.65 A maximum.
  At 15 ohms, 10 V produces ~6.67 W, still below the
  stated resistor continuous rating if load/rating are
  as supplied.
- Completion screenshot: "Completed — restoration verified",
  GUI process exited with code 0; final CH1 measured
  -0.01 V / 0.00 A; restored-state label VERIFIED; moving
  marker at 100%. These are software readbacks, not
  independent confirmation of front-panel programmed V/I.
- Final report summary screenshot:
  `hardware_demo_90s_15ohm_report_20261122_175652_376088.html`,
  run started 17:56:52 UTC: status COMPLETED;
  **495 successful readbacks**, **0 failed**, maximum logged
  setpoint lateness **2.073 ms**, output-health warnings 0,
  unexplained high readbacks 0, expected-settling
  readbacks 3, overall experiment health **OK**;
  sampled physical output MATCHED; CH1 final state VERIFIED;
  LOCAL command SENT. This summary shows logged LOCAL,
  not independently observed physical mode during this
  particular run.
- Report zoom screenshot: **8.06 W peak sampled power**,
  2.10 W mean sampled power, 259.4 J estimated energy.
  Diagnostics snapshot: `*STB?` 0/0, `LSR1?` 1/1,
  `LSR2?` 0/0, `*ESR?` 0/0, EER/QER 0/0. LSR is
  a read-and-clear event register; no continuous-mode
  claim from this register is justified.

**Status update:** Profile Runner moving position marker
and conservative CV/CC estimates are now *hardware-observed*,
with both expected CV-like and CC-like states shown after
the label-flicker fix. The real 90-second session also
passed recorded cleanup and reporting, with no readback
errors. Stronger claims about error-free indefinite operation,
instantaneous mode verification or actual hardware LOCAL
state from only the last screenshot are unwarranted.
New screenshots are current-conversation artifacts,
NOT committed PNG files in repository; do not invent
README image links.

The prior user explicitly verified physical LOCAL restoration
in an earlier run; do not silently extend that observation
to the latest 17:56 run. Original programmed CH1 V/I/enable
front-panel values after this latest run were not explicitly
reported. Only release approval remains after checking those
last physical facts if necessary and publishing image assets.
No merge or tag to `main`.


## 2026-11-22 — CV/CC label flicker fix fully offline validated

GitHub Actions **45038456180 succeeded** on `dev` source at
`583e3cd09f13587b4362d47231448abaffba7b76` with both
Python offline suite and Chromium browser validation PASS.
The new CSV cadence regression verifies that labels do not
flicker to UNKNOWN between sparse readbacks; an explicit
OFF immediately resets UNKNOWN, and CV/CC estimates change
on actual new measured values. No PSU communication, current
limit, safety or restore path was altered. The user still
needs to pull the fixed GUI to see this correction;
hardware visual validation of the post-fix UI remains pending.


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
**Repository:** `FLRHW/PSU_control`  
**Working branch reviewed:** `dev`  
**Purpose:** Persistent engineering context for future developers and ChatGPT conversations.  
**Authority:** Source code is authoritative for implemented behaviour; tests describe intended offline behaviour; historical chat/test reports are evidence of particular runs, not proof of current hardware validation.

> **Critical distinction:** This is lab automation software, **not a hardware safety interlock**. On communications failure the PSU may retain its last commanded settings. An instrument readback is not proof of terminal voltage, current, or safety.

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

## Rigol power-state dependent route audit (2026-11-16)

The user confirmed removal of HOLD text, then invoked **Inspect routes**
with Rigol powered off: the app reported "No overlapping IPv4 network
routes found." A new screenshot after powering on the Rigol underscored
that this must be interpreted as an **active-route snapshot**, not
evidence of a permanently conflict-free topology. Both direct
interfaces had previously used `169.254.0.0/16`; a host route to
Rigol `169.254.179.79` via built-in Ethernet protected DSRemote.
Do not infer the permanent routing state from one power state.

As a defensive measure, `scripts/cpx400dp_network_setup.py` now refuses
**Prepare adapter…** when a different active NIC already owns a
non-host IPv4 prefix overlapping `169.254.0.0/16`. This avoids silently
creating competing link-local routes; it does not solve persistence.
The `Inspect routes` no-overlap message now explicitly cautions about
links being down. Offline tests for the refusal and message passed in
GitHub Actions [#43960100687](https://github.com/FLRHW/PSU_control/actions/runs/43960100687)
(134 tests, 2 skips). No PSU commands, IP assignments, or route
mutations were made as part of the audit.

## v13.6 UI and route-audit increment — 2026-11-16

**User-directed UI changes on `dev`:**
- Removed the preview toolbar's `CHx initially HOLD`, `CHx HOLD:
  initial output state retained`, and `CHx OFF throughout` messages
  entirely, along with the dedicated info label. This is deliberate,
  per explicit user preference. The underlying per-channel output
  enable/HOLD semantics, CSV validation, snapshot before output changes,
  restoration and LOCAL-last logic are **unchanged**. Preview errors
  remain visible through the existing GUI status and console.
- Moved **Network settings…** to the right of the read-only Profile
  duration box on the top-right toolbar row. The left selector column
  no longer allocates a separate network-settings row.
- Added **Inspect routes** inside the existing Network settings dialog.
  It uses read-only `ip -j -4 route show table main` to flag overlapping
  IPv4 network prefixes on different interfaces, ignores explicit
  /32 host routes as conflict candidates, and reports results without
  altering OS routes, addresses, the PSU or NetworkManager.
- Tests updated in `tests/test_v13_6_network_dialog.py` and
  `tests/test_v13_6_network_setup.py` for banner removal, button
  location, nonautomatic/read-only route checks and overlapping-subnet
  detection. The current user's permanent OS configuration remains
  **untouched**.
- **Next gate:** offline CI and visual GUI confirmation, then use
  the read-only route inspection on the actual two-instrument setup.
  Only afterward design a user-approved persistent NetworkManager
  migration preserving the separate Rigol and PSU links. No automated
  OS network changes have been introduced by this increment.

## v13.6 work started — long-duration scheduling (2026-11-15)

The first development increment replaces the former eagerly materialised `schedule_for()` list with an ordered generator that combines 50 ms regular ticks, CSV keyframes and the final endpoint. `validate_schedule()` now examines regular-grid boundaries and neighbouring irregular keyframes in memory bounded by the CSV keyframe count, rather than building and inspecting tens of millions of slots. The runner records completed tick count incrementally instead of evaluating `len(schedule)`. New offline tests are in `tests/test_v13_6_long_schedule.py`, including a synthetic 1,000-hour/50 ms schedule and rejection of keyframes violating the 50 ms minimum.

**Scope:** scheduler memory scaling only. This does not yet prove end-to-end 1,000-hour operation; the report generator still loads CSV rows into memory and embeds all data in HTML. High-density keyframe performance, durable logs, recovery from outages or host shutdown, physical timing across days, and CV/CC mode display remain planned. Preserve the v13.5 verified single-socket, restoration, pause/resume and LOCAL-last invariants. Do not describe any v13.6 changes as hardware validated until the user runs the corresponding physical tests.

## v13.6 continued — chart scalability and regulation-event observation (2026-11-15)

- `cpx400dp_preview.py` plots a capped synthetic preview with time axes in seconds, minutes, hours or days, and scales the output-enable strip accordingly. GUI and report functionality remain as described in source.
- `cpx400dp_report.py` avoids JavaScript array-spread `Math.max` on large data arrays, chooses time-axis units by visible range, retains subsecond time labels for narrow windows near hour 1,000, and retains first/last/min/max samples per visible pixel bucket. It **still** loads full CSV histories and builds an embedded-JSON HTML report, so high-density 1,000-hour recordings require further architectural work for bounded memory and genuine on-demand zoom.
- Official CPX400DP command reference: [Aim-TTi CPX400DP Instruction Manual](https://resources.aimtti.com/manuals/CPX400DP_Instruction_Manual-Iss1.pdf), 'Limit Event Status' / 'Instrument Specific Commands'. `LSR1?` and `LSR2?` **read and clear** per-channel **event** status registers; 0x01 = entered CV, 0x02 = entered CC, 0x10 = entered power limit (UNREG), 0x04/0x08/0x40 = protection/trip flags. There is no continuous-current-mode proof from these event queries alone.
- New `scripts/cpx400dp_regulation.py` conservatively decodes events (CV, CC, UNREG, FAULT, UNKNOWN). The GUI shows last-observed events only; ambiguous combinations are UNKNOWN. Standalone ManualWorker queries LSR over its **own existing socket** while paused profiles query the same registers solely via the runner. No second PSU owner. Nonzero paused LSR values are recorded in the measurement CSV as `limit_event_sample` before event history clears.
- Risks: the last observed event may become stale without a transition; OFF forces UNKNOWN. The event register read clears events, so record nonzero values before clearing; never treat the indicator as a safety or protective-status guarantee. Real PSU tests must compare badge transitions with the front-panel display under safe resistive loads, including changing current limit and returning to CV.
- Offline CI for this development increment: [run #43746631345](https://github.com/FLRHW/PSU_control/actions/runs/43746631345), 110 tests, 2 expected fixture-related skips, 0 failures. No v13.6 hardware validation yet; `main` remains on v13.5.

## Network settings dialog real-device acceptance — PASS (2026-11-16)

After PyQt5 import fix, user launched the revised GUI and inspected
the Network settings dialog: layout readable, IPv4 field fully visible.
The user left the PSU IPv4 field blank; pressing **Test connection**
identified `THURLBY THANDAR, CPX400DP, 446696, 2.00-4.06` at
`169.254.51.7` via `enx0c3796303396`, auto-populated the
verified IP and confirmed `Test socket closed; profile not started`.
The user states the dialog is fine. This physically validates the
new dialog's read-only discovery/user workflow, but **does not**
validate persistent NetworkManager setup, interface renaming, reboot
behaviour or longer coexistence tests. No manual networking change
was requested by the dialog test.

## Network settings dialog import correction — 2026-11-16

The user's actual Kubuntu GUI failed on launch with
`NameError: name 'QDialog' is not defined` at
`scripts/cpx400dp_gui.py:213`: PySide6 imports contained QDialog,
but the PyQt5 fallback omitted it. Added QDialog to PyQt5.QtWidgets,
plus an offline AST test checking both supported Qt import branches.
GitHub Actions [#43926670863](https://github.com/FLRHW/PSU_control/actions/runs/43926670863)
passed 128 tests (126 passed, 2 skipped); real GUI relaunch remains to
be validated. No change to PSU commands, network routing or socket
ownership.

The Rigol hardware front-panel operates normally during DSRemote
`screen_thread.cpp line 783` errors, including reproduction with PSU
GUI closed. Investigate DSRemote waveform transfer/decoder/window
handling and instrument Ethernet communication independently; root
cause not yet established.

## v13.6 network settings dialog + independent Rigol incident (2026-11-16)

**Code (offline-tested):** Profile Runner now uses one **Network
settings…** button in place of the cramped inline IP, interface, Test
connection and Prepare adapter widgets. A 680-px-minimum-width nonmodal
dialog holds the same underlying widgets, a read-only *IDN? connection
test, status/diagnostics and opt-in NetworkManager setup. The full IP
and interface can be read without clipping; opening the dialog itself
does not send network traffic or trigger diagnostics. Instrument
ownership and safety guards remain shared with the runner and standalone
Manual Control. Source: `scripts/cpx400dp_gui.py`, with offline
structural tests `tests/test_v13_6_network_dialog.py`. GitHub Actions
run [#43925537774](https://github.com/FLRHW/PSU_control/actions/runs/43925537774)
passed. **Real GUI visual/layout acceptance is still pending**; no
new physical network configuration was attempted.

**Rigol observation, corrected:** The user initially noticed DSRemote
waveform rendering/update corruption during horizontal timebase changes
while the PSU GUI was open. Closing the PSU GUI and reconnecting DSRemote
temporarily resolved it, but the user then reproduced the same display
problem **with the PSU GUI fully closed**. The PSU GUI is therefore not
a necessary condition for the Rigol failure, and the root cause remains
unknown. Do not represent this as proven CPX400DP interference or modify
the workstation's networking to fix a possible DSRemote software fault
without supporting evidence. A diagnostic check should compare Rigol
front-panel acquisition, DSRemote connection state and network reachability
while changing timebase, independently of PSU operations.

## v13.6 hardware acceptance of retained socket — PASS (2026-11-16)

The user physically tested after synchronising the new `dev` code. PSU Test connection
identified THURLBY THANDAR CPX400DP serial 446696, firmware 2.00-4.06,
at 169.254.51.7 over Dell D6000 interface `enx0c3796303396`, with
Rigol DSRemote still updating. Standalone Manual Control displayed both
channels' programmed and measured values, then disconnected successfully.
The user subsequently executed `profiles/10.csv` with the Rigol connected.

**User-supplied actual runner evidence:** `20261116_174633_754482`:
20 s main profile, 2 s final ramp; 50 ms nominal scheduler interval;
250 ms readbacks; 401 time slots, 441 setpoint groups; maximum
scheduling lateness 0.905 ms. Initial dual-read snapshot verified:
CH1 5.000 V/1.500 A/ON; CH2 3.000 V/4.000 A/ON. 178 successful
readbacks and no failures; no unexplained high readings, one expected
settling reading, no output-health warnings. Both channel final
**programmed** states VERIFIED; sampled physical outputs MATCHED
(not a continuous terminal-voltage guarantee); `LOCAL: SENT`;
`COMPLETED — cleanup verified`, process exit code 0. HTML report
generated. The user reported that DSRemote appears to be working
normally afterward.

**Meaning:** Retained *IDN?-verified socket and short two-channel
profile/restore are now **hardware validated** with correct temporary
Rigol/PSU host routing. Do not generalise to indefinite uptime,
persistent network settings, automatic adapter migration, multi-day
profiles or untested CV/CC mode transitions. The GUI being open no
longer visibly disrupts DSRemote in this observed session, but the
earlier rendering failures warrant regression attention if repeated.
Evidence paths on user's PC:
`reports/10_console_20261116_174633_754482.log`,
`reports/10_measurements_20261116_174633_754482.csv` and
`reports/10_report_20261116_174633_754482.html`. Only Run output was
provided in chat; the full measurement/report files were not inspected.

## v13.6 connection ownership correction — 2026-11-16

**New user hardware finding:** read-only **Test connection** succeeded on
Dell D6000, but starting the runner later produced:

```text
[PSU DISCOVERED] 169.254.51.7:9221 via enx0c3796303396 —
  THURLBY THANDAR, CPX400DP, 446696, 2.00-4.06
ERROR: Discovered PSU at 169.254.51.7 on enx0c3796303396,
  but connection failed: [Errno 111] Connection refused
REPORT SKIPPED: no successful PSU readbacks were recorded
```

The original implementation first opened a short-lived `*IDN?` identity
connection in discovery and **immediately opened a second connection** for
the runner or standalone Manual Control. The log proves the first succeeded
and the second was refused; it does **not** conclusively prove whether the
PSU temporarily rejected a new session, another client was connected,
or some other transport limit was hit.

**Code correction:** `cpx400dp_discovery.identify_connection()` now verifies
the model using `*IDN?` and returns the **same still-open TCP socket**.
`discover(..., retain_sockets=True)` returns identified candidates and
owned sockets to `connect_psu()`; all unselected candidate sockets are
closed, all sockets are closed on ambiguous selection/error, and the selected
socket is passed directly to the runner/manual worker for its original-state
snapshot. No commands altering output are issued before the verified
snapshot; the runner's existing bounded snapshot retry and final
restoration/`LOCAL`-last invariants remain in force. Normal read-only
`probe()` still closes the temporary socket, ensuring that the GUI **Test
connection** never keeps ownership or starts a profile.

The runner emits an explicit `[CONNECTION NOT ESTABLISHED]` marker when the
control connection cannot be obtained, before any initial snapshot or
output control. GUI maps that case to `PSU connection failed — profile not
started` rather than claiming to have attempted or failed restoration.
No new retry occurs *after* a successful identity query; the same
connection is used. Added `tests/test_v13_6_socket_reuse.py` for selected
socket reuse, unknown-instrument closure, probe closure, ambiguous socket
closure and preflight error guards.

**Independent Rigol issue:** The user's PC had simultaneous
`169.254.0.0/16` routes through built-in Ethernet and D6000 dock,
which caused Linux to route Rigol `169.254.179.79` through the D6000
instead of `enp3s0f1`. The user added temporary
`169.254.179.79/32 dev enp3s0f1 src 169.254.10.1`; subsequent
route lookups were correct and a four-packet Rigol ping passed.
The user observed DSRemote graphics/update problems while the PSU GUI
was open, resolving after its closure. This is a **correlation, not
demonstrated software interference**. The GUI does not periodically
trigger network discovery while idle; the live hardware cause remains to
be isolated by comparing idle GUI, read-only identification and running
profile with correct routes. Do not change the system's network
configuration in response without explicit user approval.

**Validation:** GitHub Actions run
[#43920224405](https://github.com/FLRHW/PSU_control/actions/runs/43920224405)
passed **123 tests (121 passed, 2 skipped), no failures** on source commit
`1c1b52454f29ebe418e5f912c0b2a936463cb7ef`. Later backlog
and handover updates are documentation-only. **The retained-socket
code is offline-tested, not hardware-validated.**

**Next hardware checks:** sync `dev`, keep existing corrected temporary
routes, verify both instrument connection tests, then run one short
low-energy PSU profile with its outputs disconnected from a sensitive
load and confirm snapshot, output behaviour, final state verification and
LOCAL. Do not initiate another profile until the front-panel settings
have been checked after the earlier connection error. If it fails, paste
the GUI Run output in full. Preserve main as released v13.5.

## v13.6 physical identification test — PASS (2026-11-16)

**User hardware validation, read-only:** After synchronizing `dev`, the user
ran `python3 scripts/cpx400dp_gui.py`, pressed **Test connection** and
supplied GUI/console observations. The application displayed:

```text
✓ Identified THURLBY THANDAR, CPX400DP, 446696, 2.00-4.06
  at 169.254.51.7 via enx0c3796303396.
  Test socket closed; profile not started.
[PSU DISCOVERED] 169.254.51.7:9221 via enx0c3796303396 —
  THURLBY THANDAR, CPX400DP, 446696, 2.00-4.06
```

**Validated on physical PSU:** The read-only test opened a connection
through the Dell D6000 Ethernet adapter, received a matching `*IDN?`
identity, closed the diagnostic socket, and did not run a profile.
The other directly connected instrument (Rigol) remained attached.
The Qt/Wayland `QWindow::requestActivate()` warning in terminal is
unrelated to Ethernet discovery; it requires investigation only if window
focus breaks.

**NOT validated:** Standalone manual writes, profile execution/restoration
on this new revision, NetworkManager **Prepare adapter…** operation,
persistent IPv4 provisioning or discovery after reboot. The user had
previously assigned the temporary address `169.254.51.8/16` to the dock,
so discovery success does NOT establish a zero-configuration first-use
experience. A new run should test persistence/one-time setup without
changing PSU IP or disturbing the Rigol. The GUI currently disables
**Prepare adapter…** when the dock already has IPv4; that is expected.

**Next:** Evaluate NetworkManager management of the D6000 Ethernet link
and verify automatic or explicitly authorised persistent link-local setup,
then re-test the discovery button after reboot. Keep all deferred items in
[BACKLOG.md](BACKLOG.md). No merge to `main` yet.

## v13.6 network-priority increment — 2026-11-16

**Hardware topology described by user:** Rigol DS1054Z directly on workstation
Ethernet `enp3s0f1`, and CPX400DP through a Dell D6000 dock's Ethernet
`enx0c3796303396`. The Rigol has previously replied at
`169.254.179.79`; the PSU was previously verified at `169.254.51.7`.
The dock's Ethernet link was physically UP but initially had no IPv4 address,
while Linux tried to reach the PSU via the Rigol link. The user temporarily
added `169.254.51.8/16` to the dock adapter; no persistent network
configuration or completed instrument discovery test has yet been reported.
These identifiers are examples from actual tests, not defaults to impose on
all users.

**Code implemented in `dev`:**

- New `scripts/cpx400dp_network_setup.py`: enumerate up Ethernet devices
  including USB docks without IPv4, classify wired physical vs Wi-Fi/virtual,
  report read-only discovery diagnostics, and optionally create and activate
  a dedicated NetworkManager **link-local** connection only after user
  confirmation. A candidate must have carrier, be physical Ethernet, lack
  IPv4, and lack an active NetworkManager profile. The setup uses `nmcli`
  as argv (not shell), relies on user-authorised NetworkManager/Polkit, and
  does **not** change other interfaces, route tables or PSU settings.
  A failed connection activation attempts to remove the newly created
  profile. This path is **offline-tested only**, not yet exercised on the
  user's workstation.
- `cpx400dp_discovery.interfaces()` now sees connected interfaces without
  IPv4 for diagnostic/configuration purposes. Link-local TCP probes
  (`connect_on`) use `SO_BINDTODEVICE` **and bind a matching local
  169.254 source IP** to avoid selecting a source address from another
  interface when independent ports use the same /16. mDNS probes also
  select the interface's IPv4 multicast source. Existing ARP/cache/mDNS
  candidate discovery and `*IDN?` model verification remain; no
  whole-subnet sweep or unverified identity selection is permitted.
- `cpx400dp_gui.py` Profile Runner gains **Test connection**
  (asynchronous, read-only identity; temporary socket only) and
  **Prepare adapter…** (explicit confirmation before OS configuration).
  A successful unambiguous identification populates the existing PSU IP
  and interface controls, but starting a profile still opens a separate
  validated runner connection. Setup/discovery controls are unavailable
  while another worker/session owns the PSU. The CSV file dialog now
  remembers the last folder in QSettings, initially defaulting to
  the repository `profiles/` directory. No extra Qt/Python packages.
- `tests/test_v13_6_network_setup.py` includes detection of a dock
  lacking IPv4, protective setup refusal for Wi-Fi/virtual/existing-IP
  adapters, user-scoped `nmcli` commands, multiple-PSU ambiguity, and
  GUI feature guards. The existing socket binder regression was updated
  to assert explicit link-local source address binding.

**Offline evidence:** GitHub Actions run
[#43914927927](https://github.com/FLRHW/PSU_control/actions/runs/43914927927)
passed **118 tests (116 passed, 2 skipped), 0 failures** on code commit
`a43fb655076a41b99c52d1290c50176c151c8ecd`. Subsequent README and
documentation commits do not modify source/tests. **No live CPX400DP,
NetworkManager activation, GUI visual or reboot persistence test has been
performed for this increment.**

**Next controlled checks:** after syncing `dev`, launch GUI with existing
dependencies. With PSU connected via D6000 and Rigol on separate port,
select PSU IP `169.254.51.7` if still current, Interface `Auto`, and
use **Test connection**. Expect a verified `*IDN?` and correct dock interface.
If no IPv4 is present, inspect **Prepare adapter…** before accepting; it
must not propose the Rigol, Wi-Fi or an already configured adapter. After
confirmation, allow approximately 30 seconds for Auto-IP and retest.
**Do not start an energised profile before basic identity and the user's
normal safety checks.** If a setup command fails, report the exact GUI
message rather than bypassing network safeguards with ad-hoc `sudo`.

**Deferred tasks:** see [BACKLOG.md](BACKLOG.md) for VXI-11 discovery,
improvements to NetworkManager recovery, truly bounded-memory reporting,
high-resolution long-duration zoom, endurance and CV/CC hardware checks.
Do not promote `dev` to `main` until the user approves a tested release.

## 1. Project objective and environment

Control an **Aim-TTi CPX400DP** dual-channel programmable power supply from **Kubuntu/Linux**, loading a CSV profile of voltage setpoints, current limits and explicit output-enable actions. Support either stepwise or piecewise-linear profiles, sufficiently short command intervals to emulate ramps, readback logging, offline previews, interactive post-run reports and manual operation.

- Instrument transport: Ethernet/TCP, SCPI-style commands on port **9221**.
- Previously observed instrument address: `169.254.51.7` (historical example, **not** a permanent connection requirement).
- The system supports choosing an interface or auto-discovering an instrument; the discovery code verifies `*IDN?` and uses Linux interface binding where appropriate.
- The remote interface can lock instrument front-panel operation; `LOCAL` is deliberately sent last on disconnect/cleanup. A residual front-panel LOCK may need manual intervention.
- Local project directory observed in conversation: `/mnt/Data/01_Engineering/01_Projects/300_CPX400DP_control/PSU_control`.

## 2. Running and testing

Run from the repository root:

```bash
python3 scripts/cpx400dp_gui.py
PYTHONPATH=scripts python3 -m unittest discover -s tests -p 'test_*.py'
```

The GUI supports PySide6 or PyQt5. Preview generation uses Matplotlib. See `README.md` and `docs/LOCAL_SETUP.md` for installation notes; `LOCAL_SETUP.md` contains historical first-import instructions and **must not** be blindly repeated against an existing working tree.

Commit source, tests, documentation and reusable profiles; keep generated `reports/`, large oscilloscope traces and local/environment-specific files out of Git unless explicitly required.

## 3. Source layout and responsibilities

| Path | Responsibility |
| --- | --- |
| `scripts/cpx400dp_gui.py` | Qt window, profile selection/overrides, preview display, manual controls, subprocess management, UI state, console and reports |
| `scripts/cpx400dp_gui_core.py` | Qt-independent parsing of runner progress/status and preview images; run-status classification |
| `scripts/cpx400dp_run_enhanced.py` | CSV parsing, profile scheduling, commands/readbacks, pause handling, logging, restoration, diagnostics, output-health monitoring |
| `scripts/cpx400dp_manual.py` | Standalone manual-control QThread; one network socket, serialised commands, live polling and LOCAL-last disconnect |
| `scripts/cpx400dp_discovery.py` | Interface-aware instrument discovery, `*IDN?` probing, cached address/interface, TCP connection |
| `scripts/cpx400dp_preview.py` | Fully offline waveform interpretation and HTML profile preview; no instrument I/O |
| `scripts/cpx400dp_report.py` | Self-contained HTML results with interactive traces, per-channel measurements, power/energy estimates, annotations and diagnostics |
| `profiles/` | Reusable legacy/configured and waveform-only CSV profiles |
| `profiles/negative_tests/` | Deliberately invalid fixtures — **never run on hardware** |
| `tests/` | Offline regression suite |
| `docs/` | Version notes and operating guidance |

### Communication ownership

Normal profile execution uses **one TCP connection** owned by the runner. The GUI starts the runner as a subprocess; the GUI does not independently send PSU commands during a profile. Paused-profile manual requests are forwarded to the runner through a private local UNIX datagram socket; the runner alone sends those SCPI commands over its established connection. Standalone Manual Control uses its own worker/socket and must not overlap with active profile-runner ownership. Preserve this invariant.

## 4. CSV model

`load_profile()` accepts two families:

1. **Legacy CSV:** `# key=value` metadata followed by waveform rows.
2. **Waveform-only CSV:** channel columns are inferred and safe documented defaults applied; the original CSV is not rewritten by GUI overrides.

Relevant metadata includes `host`, `channels`, `mode`, `interval_s`, `readback_interval_s`, `log_file`, `ch1_restore` / `ch2_restore`, `initial_ramp_s`, `final_ramp_s`, `progress_interval_s`, `generate_report`, `report_layout` and `abort_on_output_fault`.

Waveform-only channel columns must include the full per-channel trio: `chN_voltage_v`, `chN_current_limit_a`, `chN_enable`. The loader validates the full original profile before applying a channel-selection override. Output enable directives may be explicitly ON/OFF or HOLD; **HOLD** preserves the prior output state and is not equivalent to ON.

Modes: `linear` interpolates voltage/current between keyframes; `step` holds values until the next keyframe. The initial and final ramps are distinct from the main waveform, depending on live PSU state.

Allowed schedule interval: **0.05–60 s**. Readback interval: **0.1–60 s**. The schedule validator checks all unique time slots, including irregular keyframes and end-of-phase ticks, and rejects a planned gap below **50 ms**. This is a software scheduling guard, **not** proof of the minimum reliable physical instrument command spacing.

On-run GUI overrides (selected channels, interpolation mode, step/readback intervals, ramp durations) modify only in-memory settings; they must not change profile CSV files.

## 5. Hardware protocol and command verification

Examples of command families used by the code:

- `V1 <value>`, `I1 <value>`, `OP1 0/1`: programmed channel 1 voltage/current limit/output; corresponding channel 2 forms exist.
- `V1?`, `I1?`, `OP1?`: programmed-setting readbacks.
- `V1O?`, `I1O?`: measured output readbacks.
- `*IDN?`: read-only identity verification.
- `*STB?`, `LSR1?`, `LSR2?`, `*ESR?`, `EER?`, `QER?`: diagnostic snapshots.
- `LOCAL`: final instrument command after operation/cleanup.

Before changing settings, the runner performs **two full matching programmed-state snapshots**. Reply parsing checks response type and handles bounded unexpected/stale responses rather than blindly relying on reply position. Unchanged voltage/current transmissions can be suppressed by the command optimizer; final restoration bypasses this cache.

Programmed-setting verification allows limited settling/stale replies, including retries. The stored original state must be treated separately from measured voltage/current. The final physical-output check is advisory and may be unavailable or misleading under CC mode, external loading, or output fault.

## 6. Profile lifecycle and pause/manual/resume

1. Offline-validate the selected CSV and render preview before hardware execution.
2. On Start: verify instrument identity and initial programmed states; save controlled-channel settings.
3. Execute configured initial ramp (when present), main profile, optional final ramp; log setpoint events and periodic measured values.
4. On ordinary completion, user Stop/Ctrl+C, or caught execution error: attempt configured cleanup and verify final programmed states; send `LOCAL` **last**, without subsequent PSU queries.
5. A channel with `chN_restore=true` returns to its original voltage, current limit and enable state. With `false`, cleanup commands OFF / 0 V / 0 A.
6. Stop/interrupt is not a guaranteed recovery if Ethernet or instrument communication has failed.

**Pause:** The runner's SIGUSR1 handler requests pause/resume; effective experiment time is frozen during the pause. The profile holds its latest intended programmed state. The runner continues readbacks. When pausing in the main profile, the GUI can expose **Control paused profile** in the Manual Control tab.

**Paused manual control:** A private local socket passes voltage, current-limit and output commands to the existing runner connection. Commands are validated, sent, checked against programmed readbacks and recorded in measurement events. Manual command groups are separated by at least 50 ms. Manual changes are temporary: they do not rewrite the CSV or future keyframes.

**Resume:** On resume after paused-manual changes, the runner restores and verifies the saved pause-point state before allowing the original profile to continue. If that fails, it must not quietly resume an unverified sequence; normal cleanup is attempted. Racing/outdated paused-manual requests must not be applied after resumption.

**UI behaviour inspected on `dev`:** Manual Enable/Disable buttons are enabled according to the last reported output state. The current `manual_send()` function does not ask for an enable confirmation in either standalone or paused-profile control. The Manual Control status line is intended for connection/mode/error conditions, not routine successful-command readbacks. Displayed manual voltage/current values use two decimals; internal SCPI/log precision is kept separately.

## 7. Logging and reporting

- CSV events contain UTC time, elapsed/scheduled time, event, channel, setpoint voltage, current limit, requested output state, measured V/I, scheduling lateness, readback duration and notes.
- Runner terminal output includes progress/phase, final programmed restoration status, physical-output advisory results, command traffic, scheduling metrics, readback counts, diagnostics and LOCAL transmission status.
- GUI saves console logs and displays per-channel live readbacks without opening an extra PSU socket.
- HTML reports distinguish setpoints from measured quantities, show ON/OFF and pause regions, support trace selection, wheel zoom, panning and optional Δt/ΔV cursors. Power and energy are **sampled estimates** from readback data, not independently measured transient maxima.
- Do not interpret an OFF command as proof of immediate zero terminal voltage or `LOCAL sent` as proof that the front panel is unlocked.

## 8. Output-health monitoring

The runner includes an advisory low-output monitor for output commanded ON at at least 2 V; sustained low measured voltage over multiple samples generates warnings. A profile option `abort_on_output_fault` can make a sustained fault trigger cleanup. The runner also flags unusually high measured voltage relative to commanded/recently sent values and distinguishes plausible down-step settling from unexplained readbacks. These heuristics do **not** replace an external hardware protection system or an oscilloscope measurement.

## 9. Historical hardware evidence — not a claim about current revision

The recovered previous-chat extract documents several hardware runs on 2026-11-13:

- Five representative 50 ms-update tests included a 20 V excursion, current-limit transition, step profile, long profile and dual-channel run. Reported maximum scheduling lateness: **0.772, 0.693, 0.880, 1.729 and 0.759 ms** respectively.
- A Ctrl+C test initially reported failed restoration verification after a very early readback, while later panel measurements were consistent with eventual restoration; the software was subsequently changed to poll/retry programmed-state verification.
- Other conversations describe additional real PSU testing, including pause/manual features, but evidence in the captured text is incomplete. Do not label a feature hardware-validated merely because its offline tests pass.
- The source's measured-voltage warnings and physical-output checks are not a substitute for a calibrated oscilloscope assessment of transients.

For any release, use dated report CSV/HTML/console files and record **exact Git SHA, PSU setup, loads, test procedure, pass/fail and anomalies**. No current live hardware tests were executed as part of this handover review.

## 10. Versions and authoritative status

The `dev` README and `docs/RELEASE_v13_3.md` carry a **v13.3** label. The recovered conversation reports subsequent **v13.4** usability changes and **v13.5** confirmation removal. The inspected `dev` GUI does reflect no manual enable confirmation and output-state-dependent buttons. **Do not assume README version, branch name, historical ZIP name and deployed local executable are identical.**

Before calling a state a release, run:

```bash
git status --short
git branch -vv
git log -5 --oneline
PYTHONPATH=scripts python3 -m unittest discover -s tests -p 'test_*.py'
```

Also compare Git SHA to the local working checkout and run carefully controlled hardware regression tests. This handover is a source review, **not** a fresh test execution or release certification.

## 11. Safety invariants for every change

1. No competing network connection may issue commands to the PSU while the profile runner owns it.
2. Snapshot and preserve original **programmed** values and output states before any controlled changes.
3. Never claim successful command execution, restoration or a safe output state from a write alone; require the appropriate matching readback and propagate errors.
4. Preserve intentional `HOLD` semantics for output-enable instructions.
5. Preserve the verified pause-point state and never resume after failed pause-point restoration.
6. Keep the minimum scheduled slot gap and paused-manual command-group gap at **50 ms** unless backed by new evidence and regression tests.
7. Maintain cleanup on completion, Stop, Ctrl+C and errors; do not hide partial cleanup failures.
8. `LOCAL` remains the **final PSU command** on a live connection, even when cleanup/diagnostics fail; no subsequent query may re-enter REMOTE.
9. Never substitute a readback or software alarm for physical safety protection. Treat lost communications as potentially leaving outputs energized.
10. Invalid/offline-only CSV fixtures must never be offered as runnable hardware profiles.

## 12. Outstanding checks and development priorities

- Re-run full offline tests at the actual HEAD commit; record test count and failures rather than borrowing past counts.
- Reconcile version documentation (README says v13.3; history describes v13.5), and establish an explicit release tag only after review.
- Confirm paused-manual output toggles, display state, no-confirmation controls, Resume without confirmation, correct pause-point restoration, and Stop during pause using a current, known-good low-power load.
- Test loss of Ethernet and other restoration failures **only with independent hardware-safe limits and supervision**; network failure can prevent cleanup.
- Audit command-response synchronisation, minimum spacing assumptions and behaviour near boundary scheduling slots.
- Check the documented LOCAL/LOCK distinction on the physical instrument.
- Keep generated plots, console logs and measurement CSVs for each hardware validation; reference their location and tested Git SHA in this document or a test log.

## 13. Future ChatGPT / development-session protocol

At the start of a new chat, provide the GitHub repository URL, branch and SHA, and ask for a read of **this handover**, README and relevant modules before changing source. Ask the assistant to separate **implemented**, **offline-tested**, **hardware-tested**, and **planned** work. The repository is the persistent source of truth, not the conversation.

At the end of each meaningful development session, update this document (or a compact `docs/SESSION_STATE.md`) with: current branch/SHA, changes made, tests executed/results, actual hardware tests, risks, and next actions. Commit the update with the code change; avoid a long chronological retelling.

Prefer small, reviewable Git commits and tagged, hardware-validated baselines. Keep hardware test logs outside Git if large, but record their filenames, setup and results. On future session transitions, send the next assistant only the repository link plus current `SESSION_STATE.md`; upload logs or source archives only when needed.

### New-session prompt

> Read `docs/PROJECT_HANDOVER.md`, `docs/SESSION_STATE.md` (if present), `README.md`, and the current `dev` source in `FLRHW/PSU_control`. Report the HEAD SHA, current behaviour, safety invariants and outstanding tests. Don't assume earlier ChatGPT messages are available. Before edits, check the actual implementation and existing tests; after edits, update the session file and state exactly what was offline- and hardware-tested.

---

**Handover creation scope:** Reviewed `README.md`, release/setup docs and live source of GUI, core, runner, manual worker, discovery, preview and report modules on `dev`, plus the partially recovered previous conversation. Source code was read remotely; unit tests and physical hardware were **not** executed in this review.
