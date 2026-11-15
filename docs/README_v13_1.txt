CPX400DP GUI v13.1 — paused profile manual control
==================================================

New feature: temporary manual adjustments during a PAUSED main profile.

Workflow
--------
1. Start a profile normally in the Profile Runner tab.
2. Click Pause during the MAIN PROFILE and wait for "Phase: Paused".
3. Open the Manual Control tab and click "Control paused profile".
   This does NOT open a second Ethernet connection to the PSU.
4. For selected channels, adjust voltage or current limit and click Apply;
   enable/disable an output using the explicit buttons. Programmed state
   readback is verified after each change. Monitor [PAUSE MANUAL OK] or
   [PAUSE MANUAL ERROR] in the console.
5. Click "Resume paused profile" (on the Manual tab) or the original Resume
   button. Confirm the message. The runner FIRST restores its programmed
   pause-point voltage, current limit, and output-enable state, checks them
   via readback, THEN unfreezes profile time and continues.
6. On normal completion or Stop, the original pre-run settings are still
   restored using the existing runner cleanup. LOCAL remains last.

Important design choices
------------------------
- Manual control of a paused profile is available only during the main CSV
  phase (not initial/final ramps or restoration).
- Only channels included in the active profile are adjustable while paused.
- Changes made manually during Pause are TEMPORARY: they do not change the
  CSV, the saved initial settings, or the rest of the programmed profile.
- "Leave paused controls" exits the manual tab's command mode but does NOT
  restore the held profile settings. Resume or Stop performs restoration.
- The profile runner is the only owner of the PSU Ethernet connection. The
  GUI sends local commands through a private UNIX-domain datagram socket
  (private /tmp directory with 0700 permissions, socket 0600).
- Setpoint writes are rate-limited to >=50 ms between manual command groups.
- Manual commands and verification are logged to the measurement CSV; manual
  setpoints are included in HTML report traces, and pause remains shaded.
- A failed pause-point restore aborts further profile progress and attempts
  the standard pre-run restoration, then LOCAL. Check the PSU manually if
  final verification is not successful.
- While running (not paused), the standalone Manual Control connection is
  disabled; the runner and stand-alone worker never compete for the PSU.

Hardware validation
-------------------
This build passed simulated runner, pause/manual, command ordering and GUI
transport tests. Real Qt GUI interaction and PSU hardware tests must still be
performed on the user's Kubuntu workstation, starting at low safe voltages
and with a controlled load. This is laboratory automation, not a safety
interlock.

Inherited from v13
------------------
Basic stand-alone manual control, waveform-only CSVs, optional legacy CSV
metadata, persistent user-selected scheduling/ramp defaults, channel subset
selection, reports, automatic Ethernet interface discovery, stop/pause,
final-state verification, and LOCAL-last cleanup.
