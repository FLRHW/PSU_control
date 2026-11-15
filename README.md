# CPX400DP PSU Control

**Current development baseline: v13.5 behaviour on `dev` (not a hardware-validated release).**  
**Stable/imported baseline: v13.3 on `main`.**

Linux/Kubuntu Python control application for Aim-TTi CPX400DP PSU, supporting CSV profile execution, pause/manual/resume, Ethernet discovery, interactive reports and standalone manual control.

## Version status

| Version | Branch / evidence | Status |
| --- | --- | --- |
| v13.3 | Imported application baseline on `main`; `docs/RELEASE_v13_3.md` | Historical import/release label; not revalidated by this documentation update |
| v13.4 | Subsequent changes on `dev`; `docs/RELEASE_v13_4.md` | Historical development milestone: output-state buttons, coloured indicators, confirmation-free Resume |
| v13.5 | Current `dev` source and `docs/RELEASE_v13_5.md` | Working development baseline: also removes standalone Manual Control output-enable confirmation; **full regression and hardware release validation pending** |

Version numbers above describe **feature milestones**, not Git tags or automatic evidence that a physical PSU was tested with that exact commit. Source on `dev` was reviewed, but no unit tests or physical PSU tests were executed as part of the version reconciliation.

## Documentation to read first

- [Engineering handover](docs/PROJECT_HANDOVER.md): architecture, protocol, safety invariants, decisions, historical evidence
- [Session state](docs/SESSION_STATE.md): current development status, validation gaps and next steps
- [v13.5 development notes](docs/RELEASE_v13_5.md): current manual-control behaviour and evidence
- [v13.4 historical notes](docs/RELEASE_v13_4.md), [v13.3 historical notes](docs/RELEASE_v13_3.md)

## Layout

- `scripts/` — application and SCPI modules
- `profiles/` — reusable legacy and waveform-only CSV profiles
- `profiles/negative_tests/` — **deliberately invalid fixtures; never run on hardware**
- `tests/` — offline regression suite
- `docs/` — operating instructions, handover, session state and release history
- `reports/` — untracked local output (measurement logs, reports, etc.)

## Run

```bash
python3 scripts/cpx400dp_gui.py
```

Choose a profile from `profiles/` using the GUI. Set the output folder to `reports/` for generated files.

## Tests

```bash
PYTHONPATH=scripts python3 -m unittest discover -s tests -p 'test_*.py'
```

Manual voltage/current spinboxes and displayed live V/A values show two decimal places. Internally stored precision, SCPI payloads, and logged measurements are not rounded by this display-only change.

## Git and safety

Only version-control scripts, profiles, tests and documentation. `reports/` and large scope CSVs are excluded. Keep secrets and local connection details out of commits.

**This is laboratory automation, not a hardware safety interlock.** A failed connection may leave outputs at their last settings. Preserve the verified restoration and `LOCAL`-last behaviour when making changes; consult the handover.
