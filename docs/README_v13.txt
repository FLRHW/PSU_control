CPX400DP v13 — Manual Control + simpler waveform CSV
=======================================================

Run from the extracted directory:
  /usr/bin/python3 cpx400dp_gui.py

Dependencies: the same Qt and matplotlib packages as the v12.x GUI.
No new dependencies are required. On Kubuntu the previous install command
was: sudo apt install python3-pyqt5 python3-matplotlib

WHAT CHANGED
------------
* The application now has Profile Runner and Manual Control tabs.
* Manual mode connects via the established interface-aware discovery,
  snapshots both channels and displays programmed and measured values.
* Separate voltage/current Apply controls and explicit output ON/OFF buttons
  are available for CH1/CH2. Turning output ON requires confirmation.
* Changes are verified against programmed-state readbacks, not assumed.
* Manual mode holds its own single socket on a worker thread. Profile
  execution is disabled while it holds the instrument; manual connection
  cannot begin during an experiment.
* Disconnect preserves user-entered programmed settings and outputs, sends
  LOCAL as the final SCPI command and closes the socket. Disconnect does NOT
  restore the values that were present before connecting in manual mode.
  A lost network connection may prevent LOCAL; inspect the PSU if warned.
* In the Profile Runner, settings for interpolation, setpoint step interval,
  readback interval, initial/final ramps are now application defaults that
  remain editable irrespective of the channel-selection checkbox and are
  remembered using QSettings (per-user config).
* The checkbox now controls ONLY channel subset selection. Untick it to
  run all channels contained in the waveform CSV. It cannot activate a channel
  without waveform columns in that file.
* New CSVs can contain ONLY waveform columns and rows. No # key=value
  metadata is necessary. Both original and simplified files remain supported.
* Initial GUI defaults are linear, 50 ms setpoints, 250 ms readbacks,
  0 s initial ramp and 2 s final ramp; edit to suit your load.
* Legacy CSV metadata remains honoured in direct command-line runs. From
  the v13 GUI, persistent application defaults override its timing/mode/ramp
  values, with no modification to the CSV.

SIMPLIFIED WAVEFORM CSV EXAMPLE
-------------------------------
time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable
0,2.0,1.5,0
0.5,2.0,1.5,1
1.0,5.0,1.5,hold
2.0,2.0,1.5,0

For dual-channel CSVs add these three columns:
 ch2_voltage_v,ch2_current_limit_a,ch2_enable

At least one fully defined channel is required. All rows have time_s.
Valid enable: 0,1,hold,keep,or blank. Voltage 0–60 V and current 0–20 A.
Time must start at 0 and increase strictly. Scheduled setpoint spacing
remains >= 50 ms; measurement interval is >= 100 ms.

Defaults for a waveform-only CSV used from the CLI (no GUI settings):
  host = 169.254.51.7, mode=linear, steps=0.05 s, readbacks=0.25 s,
  ramps=0 s, restore original programmed state for each channel,
  write <profile>_measurements.csv, report enabled.
Discovery uses *IDN? to identify the PSU. Pass --psu-ip/--psu-interface
or use the GUI connection field if your instrument address differs.
The fallback host is only a discovery candidate, not a guaranteed device.

Use 15_waveform_only.csv or 17_irregular_setpoint_spacing_waveform_only.csv
for examples. For 17, choose STEP interpolation in the app defaults.

SAFETY / TESTING
----------------
The 50 ms/100 ms minima, error monitoring and original programmed-state
restoration of the PROFILE runner are retained. LOCAL is the last PSU SCPI
command during cleanup. The manual panel is not an emergency stop or a
physical safety interlock. Observe hardware power/load limits.

The offline regression suite includes parser compatibility and manual
protocol simulation. This release has not been exercised against a live
CPX400DP or visually verified in a real Qt desktop in the build environment.
Before using substantial power, verify the manual panel using low voltages
with the output initially OFF. Disconnect and confirm the front panel
returns to local control.
