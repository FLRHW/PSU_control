CPX400DP GUI v12.2 — 15 November 2026
====================================

Start: /usr/bin/python3 cpx400dp_gui.py

Changes from v12.1
------------------
1. CH1 / CH2 checkboxes moved into the Override CSV row (as requested).
   - Override unchecked: boxes show CSV-selected channels and are disabled.
   - Override checked: choose any nonempty subset of CSV-defined channels.
   - A channel absent from the CSV cannot be enabled by an override.
   - The CSV source is never modified. The runner validates ALL original
     columns/settings before selecting a subset, including restore policies.
   - CH1-only CSV 17 can only run CH1. Dual-channel CSV 15 can run CH1,
     CH2, or both, with correct per-channel original-state restoration.
2. Main profile duration is in the read-only box alongside preview buttons.
3. Unchecking Override CSV resets edited channel, timing and mode fields to
   values from the current CSV. Changing CSV resets overrides too.
4. Single-channel previews have bounded dimensions in the scrollable GUI.
   Corrected missing NUMERIC time-axis labels: the output-state strip no
   longer accidentally suppresses ticks on the main chart's shared axis.

Safety and scope
----------------
- Original discovery, scheduling, 50 ms minimum setpoint timing, 100 ms
  minimum readback timing, settling detector, diagnostics, safety checks,
  and final-state restoration remain unchanged.
- Channel-subset selection is a new runner override. No channels absent from
  the source CSV may be activated. At least one channel must be selected.
- Local is sent last as in prior releases.
- Do NOT execute *REJECT* offline-only test profiles on hardware.

Offline validation
------------------
  python3 -m unittest discover -q
  python3 cpx400dp_run_enhanced.py 17_irregular_setpoint_spacing.csv --preview
  python3 cpx400dp_run_enhanced.py 15.csv --channels 1 --preview

UI smoke checks on Kubuntu
--------------------------
- Load 17_irregular_setpoint_spacing.csv: CH1 checked, CH2 disabled; numeric
  0..8-second labels should be visible below the voltage chart.
- Load 15.csv; Override CSV ON: CH1/CH2 may be unchecked separately, but
  at least one must remain selected. The preview should reflect selection.
- Change readback 0.250 -> 0.100 s, uncheck Override CSV: displays 0.250 s.
- The duration field displays main profile duration, not optional ramp time.

Requires the same Python/Qt/matplotlib packages as v12.1. No new packages.
The Rigol exporter is standalone and not required by this application.
