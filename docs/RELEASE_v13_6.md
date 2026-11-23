# CPX400DP Control v13.6

**Published:** 22 November 2026  
**Release:** [v13.6](https://github.com/FLRHW/PSU_control/releases/tag/v13.6)

This is the first public release of CPX400DP Control, a Linux desktop application for controlling an Aim-TTi / Thurlby Thandar CPX400DP dual-output power supply over Ethernet. It supports manual operation, programmable CSV experiments and measurement recording.

## Included in this release

- **Profile Runner:** Execute one- or two-channel voltage and current-limit profiles from CSV, with step or linear interpolation, configurable command/readback intervals, output-enable control, and initial/final ramps.
- **Manual Control:** Adjust voltage, current limit and output state. Pause a running profile for temporary manual changes and resume from the held profile settings.
- **Instrument connectivity:** Identify the PSU, select its network connection and remember the last verified address and interface.
- **Live monitoring:** Display measured voltage and current, conservative CV/CC estimates, and a moving position marker over the profile preview.
- **Experiment reports:** Record readings and control events, then explore voltage, current and power in HTML reports with selectable traces, zoom, cursors and timing annotations. Large recordings use local companion data files for on-demand detail.
- **Recording utilities:** Read-only audit of completed or interrupted logs, advisory free-space warnings and an optional checksummed archive command that does not delete source files.
- **KDE integration:** A scalable application icon and user-local KDE Plasma launcher installer.
- **Example profiles:** Short experiments and sparse long-duration schedules for exploring the preview and profile runner.

## Install and launch

From a checkout of the project, with Python 3, PyQt5 or PySide6, and Matplotlib installed:

```bash
/usr/bin/python3 scripts/install_desktop_launcher.py
```

Search for **CPX400DP Control** in KDE's Application Launcher. Alternatively:

```bash
/usr/bin/python3 scripts/cpx400dp_gui.py
```

See the [README](../README.md) for current installation instructions, screenshots and examples. The README tracks the latest `main` branch and may include improvements made **after** this tagged release.

## Validation and limitations

Version v13.6 was exercised with supervised CPX400DP hardware experiments, including profile execution, pause/manual/resume, CV/CC estimation and programmed-state restoration. Python regression tests and Chromium report-browser tests passed before publication.

The software is intended for laboratory automation, not as an independent safety interlock. Restoration attempts to return the instrument to its **previous programmed settings**, including an enabled output if it was enabled beforehand. Loss of communication or power can prevent restoration or verification; actual output state must be checked on the instrument when necessary. CV/CC indicators in the Profile Runner are estimates derived from readings, not continuous hardware-mode telemetry. Multi-day unattended operation and recovery after sudden power loss have not been physically validated.

## Release scope

These notes describe **the v13.6 tag**, not every later commit on `main`. Subsequent README improvements, profile-example cleanup, and KDE window/taskbar identity updates are post-release work and will be accounted for in the next version's release notes. The published v13.6 tag is unchanged.
