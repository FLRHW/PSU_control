# CPX400DP controller — engineering handover

**Updated:** 2026-11-16  
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
