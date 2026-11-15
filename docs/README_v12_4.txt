CPX400DP GUI v12.4 — display-only maintenance update

Compared with v12.3:
- An excluded channel shows "N/A — channel not selected", instead of "Restoration: pending". This applies when starting and completing channel-subset runs, and when idle settings are changed or reset.
- When only one profile preview channel is visible, the chart is horizontally centred while retaining its bounded dimensions.
- Runner, discovery, SCPI protocol, logging, CSV parsing and HTML report remain unchanged.

Validation: 71 Python offline tests passed on 2026-11-15. This environment did not provide a Qt GUI or physical instrument for a live test.

Run: python3 cpx400dp_gui.py

Possible v13 scope: separate virtual manual PSU control panel, with mutual exclusion against automatic profile execution, explicit output enable, confirmation for dangerous output changes, live readbacks, and deterministic LOCAL/connection release. This is not implemented in v12.4.
