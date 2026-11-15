# CPX400DP — current session state

**Updated:** 2026-11-15  
**Project:** `FLRHW/PSU_control`  
**Active development branch:** `dev`  
**Stable release branch:** `main` (v13.5 merged from `dev`, PR #1, merge commit `7d5b3931404a9630c0343808e3ac7f695b289516`).  
**Functional milestone:** **v13.6 development started**. v13.5 functional hardware acceptance completed and merged to `main`; v13.6 code is offline-only and not hardware validated.  
**Source baseline:** v13.6 code through `16054d124f864b634968bfd44a11331672ba72cf` (later documentation-only changes; always check current `dev` HEAD).

> This file is a compact start-of-session index. For full technical architecture, safety invariants and historic test evidence read [PROJECT_HANDOVER.md](PROJECT_HANDOVER.md). For milestones read [RELEASE_v13_5.md](RELEASE_v13_5.md) and previous release notes.

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

1. On workstation: `git switch dev && git pull`, then `git status --short && git rev-parse HEAD`.
2. Assistant checks the automated offline regression for each new `dev` commit before requesting any hardware test; reference successful CI run #43734073069 for the documented baseline. The user is responsible only for physical hardware measurements and interactions.
3. **v13.5 release merged.** v13.6 current code has CI pass at `16054d1` (110 tests, 2 skipped); next tackle bounded-memory reporting and hardware-focused CC/CV verification when ready. User performs only physical hardware checks.
4. Before any v13.6 release, complete bounded-memory report/log processing and offline stress tests; then request limited, controlled hardware validation of CV/CC last-event indicators, pause/manual integration and 50 ms scheduler. Keep `main` on v13.5 until explicitly approved.
5. After each meaningful development/testing session, update this file with commit, results, unresolved items and next action. Prefer a short state (about one page) over entire chat histories.

## Start-of-next-chat prompt

> Inspect `FLRHW/PSU_control` branch `dev`, starting with `docs/SESSION_STATE.md` and `docs/PROJECT_HANDOVER.md`. Verify current HEAD and implementation before editing. Keep `main` unchanged unless explicitly requested. Preserve single instrument-socket ownership, pause-point verification, final restoration and LOCAL-last. After work, update session state with exact tests performed and current limitations.
