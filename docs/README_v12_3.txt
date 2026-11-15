CPX400DP GUI v12.3 — presentation/status maintenance release

Changes since v12.2:
- Selecting another CSV, or changing any CSV override while idle, clears the
  previous run's measured V/I displays, restoration status, progress and phase.
  Prevents stale historical results from appearing to belong to a new profile.
  The console history and saved run artifacts remain untouched. No PSU commands
  are issued by this display reset.
- Disable polling of the previous run's measurements when the displayed
  profile/overrides change.
- Increased clearance between the main preview chart's numeric time-axis title
  and the output-state strip; labels stay inside the strip.

Unchanged:
- Instrument runner and network discovery, setpoint/readback scheduling,
  safety checks, restoration behaviour, LOCAL-last logic, reporting.
- CSV override rules and channel-subset handling from v12.2.

Validation:
- 67 offline unittest cases pass, including 2 new stale-status regression tests.
- Generated and visually inspected preview images for 15.csv and 17.csv.
- No Qt desktop or physical PSU hardware verification in this environment.

Run: /usr/bin/python3 cpx400dp_gui.py
