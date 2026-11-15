# CPX400DP controller — engineering handover

**Updated:** 2026-11-15  
**Repository:** `FLRHW/PSU_control`  
**Working branch reviewed:** `dev`  
**Purpose:** Persistent engineering context for future developers and ChatGPT conversations.  
**Authority:** Source code is authoritative for implemented behaviour; tests describe intended offline behaviour; historical chat/test reports are evidence of particular runs, not proof of current hardware validation.

> **Critical distinction:** This is lab automation software, **not a hardware safety interlock**. On communications failure the PSU may retain its last commanded settings. An instrument readback is not proof of terminal voltage, current, or safety.

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
