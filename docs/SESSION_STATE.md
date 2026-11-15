# CPX400DP — current session state

**Updated:** 2026-11-15  
**Project:** `FLRHW/PSU_control`  
**Active development branch:** `dev`  
**Stable/import branch:** `main` (v13.3 import; no merge performed)  
**Functional milestone:** **v13.5 development behaviour**, not yet a hardware-validated stable release.  
**Source baseline examined for handover:** `a118b9e0ede1c496101dd46bbe3e3f602cd25601` on `dev` (documentation-only commits follow; **check current HEAD** before writing code).

> This file is a compact start-of-session index. For full technical architecture, safety invariants and historic test evidence read [PROJECT_HANDOVER.md](PROJECT_HANDOVER.md). For milestones read [RELEASE_v13_5.md](RELEASE_v13_5.md) and previous release notes.

## Currently implemented in dev

- Qt Profile Runner and Manual Control tabs, configurable CSV-driven stepped/linear profiles, offline preview and interactive HTML measurement reports.
- Ethernet PSU discovery and interface selection, verified programmed-state snapshots, command/readback parsing, output-health monitoring and cleanup.
- Pause/manual/resume via runner-owned TCP socket and local IPC; pause-point restoration and verification before resuming.
- Manual output state shown prominently as green ON, red OFF or grey unknown; Enable/Disable actions unavailable when redundant or state unknown.
- No confirmation popup for output enabling in standalone or paused-profile Manual Control, and none on Resume.
- Two-decimal manual V/A display without rounding internal communication/log values.

## Branch/version reconciliation

- `main` has imported **v13.3** baseline (verified with GitHub branch comparison; base commit `db872a89648551d73788af3ad46e97b61c8ba2e6`).
- `dev` carries the v13.4 UI milestone and v13.5 confirmation-removal milestone plus documentation updates.
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
- **Stage 2 — PENDING:** Pause a safe, simple running profile; temporarily change voltage/output using paused-profile manual controls; verify readbacks and correct restoration of the held pause-point state before confirmation-free resume. Confirm experiment time excludes pause and final restoration succeeds. Record console/measurements/report.
- **Stage 3 — PENDING:** Stop during live execution/paused state, verify programmed restoration, LOCAL-last and reporting.
- Do not merge to `main` solely on Stage 1.

## Next-revision enhancement request (user observation, 2026-11-15)

- **Display per-channel CV / CC regulation status in the Manual Control tab**, including standalone Manual Control and, if practical, paused-profile Manual Control. Current UI shows programmed state, measured voltage/current, and ON/OFF, but not CV/CC.
- Do **not** infer the mode merely from a comparison between measured voltage and current limit. First consult the CPX400DP programming manual to identify an authoritative per-channel status query/register and the actual CV/CC bit semantics; `LSR1?` / `LSR2?` are currently collected as raw diagnostic queries by the runner, but their bit fields have not been validated here.
- Display **CV**, **CC**, or **Unknown / unavailable** where appropriate (including OFF or ambiguous readbacks); do not misrepresent unknown as CV.
- Preserve the instrument's single-socket ownership: standalone manual worker should query on its existing socket; paused-profile manual control must route through the active runner, not open a competing connection.
- Keep status queries non-disruptive, check whether any status registers are clear-on-read, avoid degrading 50 ms profile scheduling or interfering with existing diagnostics. Add mocked protocol, state/UI, and no-extra-socket offline tests before any hardware trial.
- **Deferred until the next software revision.** This entry changes documentation only; Stage 2 and Stage 3 v13.5 testing remain on the current unchanged code.

## Known validation evidence and gaps

- Historical v13.4 session: reported **94 offline tests passed**; hardware and GUI visual validation were outstanding at that point.
- Historical v13.5 session: reported **six focused handler checks passed**, but **full regression suite not run**.
- Older 50 ms scheduling runs and Ctrl+C restoration investigations are covered by the handover; they are evidence for past versions, not a substitute for v13.5 validation.
- Current `dev` offline suite **passed at commit `69d0e0c`** (95 tests, 2 skipped for unavailable hardware recordings); future source changes require a fresh CI result. Hardware Stage 1 passed by user report; Stages 2 and 3 remain pending. Verify local working tree matches remote branch before hardware testing.
- Software is not a fail-safe protection mechanism; loss of LAN can prevent restoration.

## Next actions, in order

1. On workstation: `git switch dev && git pull`, then `git status --short && git rev-parse HEAD`.
2. Assistant checks the automated offline regression for each new `dev` commit before requesting any hardware test; reference successful CI run #43734073069 for the documented baseline. The user is responsible only for physical hardware measurements and interactions.
3. **Stage 1 completed (user-reported).** Next request hardware Stage 2: pause/profile manual changes/verified resume and timing. Then Stage 3: Stop/restoration/LOCAL. Record report CSV/HTML/console and actual PSU load.
4. If successful, decide on merge of `dev` to `main` and a formal version/tag; do not treat docs changes as validation.
5. After each meaningful development/testing session, update this file with commit, results, unresolved items and next action. Prefer a short state (about one page) over entire chat histories.

## Start-of-next-chat prompt

> Inspect `FLRHW/PSU_control` branch `dev`, starting with `docs/SESSION_STATE.md` and `docs/PROJECT_HANDOVER.md`. Verify current HEAD and implementation before editing. Keep `main` unchanged unless explicitly requested. Preserve single instrument-socket ownership, pause-point verification, final restoration and LOCAL-last. After work, update session state with exact tests performed and current limitations.
