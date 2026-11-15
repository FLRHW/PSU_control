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
- Workflow added in commit `06dbdd3fbfc40e280da5cfd998c8c1de9b3a5921`; workflow result has **not yet been independently retrieved**. Do not record the suite as passing until an actual run is inspected.
- Policy: assistant handles code-only/offline regression, simulation and CI; user handles physical-CPX400DP/oscilloscope/load validation only.

## Latest work (2026-11-15)

- Reviewed key source files (`cpx400dp_gui.py`, `cpx400dp_gui_core.py`, `cpx400dp_run_enhanced.py`, `cpx400dp_manual.py`, `cpx400dp_discovery.py`, `cpx400dp_preview.py`, `cpx400dp_report.py`) against the partial exported prior conversation.
- Committed `docs/PROJECT_HANDOVER.md` on `dev` at `a118b9e`.
- Added v13.5 development notes and reconciled README version/status.
- Established this `SESSION_STATE.md`.
- **No source or test code changed, no automated tests executed, no physical PSU tests performed during this documentation session.**

## Known validation evidence and gaps

- Historical v13.4 session: reported **94 offline tests passed**; hardware and GUI visual validation were outstanding at that point.
- Historical v13.5 session: reported **six focused handler checks passed**, but **full regression suite not run**.
- Older 50 ms scheduling runs and Ctrl+C restoration investigations are covered by the handover; they are evidence for past versions, not a substitute for v13.5 validation.
- Current `dev` full-suite pass and physical verification **remain pending**. Verify local working tree matches remote branch before testing.
- Software is not a fail-safe protection mechanism; loss of LAN can prevent restoration.

## Next actions, in order

1. On workstation: `git switch dev && git pull`, then `git status --short && git rev-parse HEAD`.
2. Run offline regression: `PYTHONPATH=scripts python3 -m unittest discover -s tests -p 'test_*.py'`; record actual outcome and exact HEAD here.
3. Run low-power hardware checks: standalone ON/OFF and indicators; paused-profile manual changes, Resume restoration, Stop during pause, no popup dialogs, final `LOCAL`. Record report CSV/HTML/console and actual PSU load.
4. If successful, decide on merge of `dev` to `main` and a formal version/tag; do not treat docs changes as validation.
5. After each meaningful development/testing session, update this file with commit, results, unresolved items and next action. Prefer a short state (about one page) over entire chat histories.

## Start-of-next-chat prompt

> Inspect `FLRHW/PSU_control` branch `dev`, starting with `docs/SESSION_STATE.md` and `docs/PROJECT_HANDOVER.md`. Verify current HEAD and implementation before editing. Keep `main` unchanged unless explicitly requested. Preserve single instrument-socket ownership, pause-point verification, final restoration and LOCAL-last. After work, update session state with exact tests performed and current limitations.
