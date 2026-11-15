CPX400DP GUI v12 — Nov 15, 2026
=================================

v12 changes
-----------
1. Interface-aware discovery (cpx400dp_discovery.py). Before starting the
   instrument control session, read-only *IDN? queries identify CPX400DP on
   relevant active Linux interfaces. The app checks CSV host, cached host,
   ARP neighbour table and optional mDNS (_lxi._tcp.local) responses. A TCP
   socket is bound to the selected interface using SO_BINDTODEVICE, so a
   competing 169.254/16 default route will not send commands to the wrong NIC.
   This needs no sudo, route changes, pip dependencies or Avahi packages.
   Last working IP/interface are cached in ~/.config/cpx400dp/last_psu.json.
   Manual IPv4 and interface overrides are in the GUI toolbar.

   Discovery never changes PSU voltage/current or outputs; only *IDN? is sent.
   The separate discovery connections are closed before the original runner
   takes control. *IDN? confirms model, not unique instrument identity; if
   multiple PSUs respond, use the manual IP/interface selection.

   Discovery does not blindly scan 65,536 link-local addresses. If the PSU IP
   changes AND mDNS is unavailable or returns no address, manually enter the
   currently assigned IP. The CPX400DP and PC must be on a reachable link.
   Linux/iproute2 is assumed (standard Kubuntu install).

2. Standalone interactive HTML report: wheel zoom (pointer anchored), drag to
   pan, Cursors ON then two clicks for A and B; cursor readouts give delta t
   and delta V from nearest PSU measured-voltage samples. Reset zoom restores
   the full view and clears cursors. Separate channel controls; other traces
   remain independently selectable. The report loads completely offline.
   Measurements remain 250-ms sampled readbacks; cursor precision is not
   oscilloscope-grade and nearest readback is explicitly used.

3. Simplified GUI profile summary: 'Ch 1, 2 · 20 s'. Minimum scheduled gap
   is still validated by the runner and recorded in the console log.

Unchanged protections
---------------------
- Minimum 50-ms scheduled voltage/current update interval plus phase-gap guard.
- Initial double snapshot, optional ramps, readbacks, diagnostics.
- Pause/resume, Stop, restoration and LOCAL last command.
- v11.1 settling-aware anomaly detector and health classification.
- Offline rejection profiles should NEVER be executed on hardware.
- The PSU software is laboratory automation, NOT an independent safety interlock.

Launch on Kubuntu
----------------
  /usr/bin/python3 cpx400dp_gui.py

Existing prerequisites: Qt bindings (PyQt5 or PySide6), Python3, matplotlib
for offline profile graphics. No NEW system packages are needed for v12.

Manual discovery (does NOT change outputs):
  python3 cpx400dp_discovery.py --ip 169.254.51.7

Runner manual selection:
  python3 cpx400dp_run_enhanced.py 15.csv --psu-ip 169.254.51.7 \
      --psu-interface enx0c3796303396

Offline preview (never connects):
  python3 cpx400dp_run_enhanced.py 15.csv --preview

Offline tests:
  python3 -m unittest discover -v

HTML report from an existing recorded CSV (no PSU connection):
  python3 cpx400dp_report.py 15_measurements_20261115_085658_842524.csv

The independent Rigol DS1054Z developer tool is NOT part of this application;
it is supplied as a separate ZIP, and is optional for normal PSU use.

Hardware validation
-------------------
- On a machine with multiple link-local NICs, start v12 with an empty IP and
  interface override. The console should show '[PSU DISCOVERED]' including
  correct IP, NIC and *IDN? identity before '[SNAPSHOT VERIFIED]'.
- Run existing 15.csv at the same 15-ohm CH1 / unloaded CH2 conditions if safe.
- Confirm restored programmed settings and LOCAL-last in the console log.
- Open report in browser; test zoom, pan, cursors and Reset.
- Optionally remove the temporary /32 route introduced during v11.1 testing
  to prove interface binding works without it, ONLY after ensuring a later
  hardware run is safe; routing must not be changed while an experiment runs.


V12.1 GUI-only additions (control runner unchanged):
- Read-only CH1/CH2 channel selection indicators beside preview controls.
- Profile duration displayed in a read-only field.
- Disabling Override CSV immediately restores CSV values; re-enabling starts
  with CSV defaults; changing CSV also clears overrides.
- In-window preview images retain bounded size (<=650 px wide, <=350 px high),
  full time axis, and consistent size with one or two channels.
- v12 runner, communication, 50 ms setpoint and 100 ms readback minima unchanged.
