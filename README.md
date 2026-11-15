# CPX400DP PSU Control

Python-based controller for the Aim-TTi CPX400DP power supply. Includes a profile runner, virtual manual-control panel, Ethernet discovery, logging, HTML reports, and offline tests.

## Repository layout

- `scripts/` — executable Python application modules
- `profiles/` — reusable waveform CSV profiles; `profiles/negative_tests/` contains deliberately invalid examples (do not run on hardware)
- `tests/` — offline regression tests
- `docs/` — operating notes and historical release instructions
- `reports/` — local generated measurements, console logs, plots and HTML reports (**ignored by Git**)

## Start

On Kubuntu, from the repository root:

```bash
python3 scripts/cpx400dp_gui.py
```

Run offline tests:

```bash
PYTHONPATH=scripts python3 -m unittest discover -s tests -p 'test_*.py'
```

The application may need a compatible Qt binding and matplotlib. Consult `docs/` for requirements and details. Avoid running deliberately invalid profiles on live hardware.

## Source of truth

Commit application source and reusable profiles. Keep generated reports and large scope captures local, outside Git history. Hardware-output commands can energize loads; verify programmed limits and output enable states before testing.
