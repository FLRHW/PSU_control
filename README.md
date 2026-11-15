# CPX400DP PSU Control — v13.3

Linux/Kubuntu Python control application for Aim-TTi CPX400DP PSU, supporting profile execution, pause/manual/resume, Ethernet discovery, interactive reports and standalone manual control.

## Layout

- `scripts/` — application and SCPI modules
- `profiles/` — reusable legacy and waveform-only CSV profiles
- `profiles/negative_tests/` — **deliberately invalid fixtures; never run on hardware**
- `tests/` — offline regression suite
- `docs/` — operating instructions and release history
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

## Formatting change

The manual panel's voltage/current spinboxes and live displayed V/A values now show **two decimal places**. Internally stored precision, SCPI payloads, and logged measurements are not rounded by this display-only change.

## Git

Only version-control scripts, profiles, tests and documentation. `reports/` and large scope CSVs are excluded. Keep secrets and local connection details out of commits.
