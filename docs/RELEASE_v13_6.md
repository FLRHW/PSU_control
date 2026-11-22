# CPX400DP Control v13.6 — release notes

**Target release date:** 22 November 2026.  
**Source:** `dev`, merging to `main` after final CI acceptance.  
**Scope:** Linux/Kubuntu GUI, CSV profile automation, reports and offline tooling.

## Changes since v13.5

- Integrated Linux network discovery and verified last-known PSU IPv4/interface persistence, without changing existing interface configuration.
- Improved manual control and paused-profile adjustments, with verified settings and resume restoration.
- Lazy scheduling of very long sparse-keyframe profiles and seconds-through-days offline preview axes.
- Moving magenta NOW marker over the profile preview, pausing with the profile.
- Conservative Profile Runner `CV likely` / `CC likely` estimates based on already recorded programmed and measured values. **Not an independent hardware mode readback.**
- Clearer post-run display, distinguishing programmed restored V/current **limit**/output enable from independently sampled post-restore voltage. No false 0 V / 0 A display from stale pre-restoration measurements.
- Streaming HTML report for large CSVs (local companion chunks, file:// open, time jumping, 50 ms spike navigation, zoom/pan/cursors).
- Read-only recording audit for normal and interrupted logs, advisory low-disk monitoring and simulated disk-write-failure containment around PSU cleanup.
- Optional checksummed ZIP archiving of finished recording, report HTML and chunk folder; original logs are never deleted automatically.
- Sparse 24-hour, seven-day, 1,000-hour offline preview examples; supervised low-voltage and 15 Ω resistive-load demo examples.
- New scalable dual-channel PSU application icon and **user-local KDE Plasma launcher installer** `scripts/install_desktop_launcher.py`.

## Install launcher

```bash
/usr/bin/python3 scripts/install_desktop_launcher.py
```

Then search `CPX400DP Control` in KDE's Application Launcher,
pin it to the taskbar or add a keyboard shortcut. Install into the
checkout you want to run; moving the checkout requires rerunning the
installer. Remove with `--uninstall`. No root privileges, desktop
environment modifications outside XDG user directories, or extra Python
dependencies.

## Validation evidence

- GitHub Actions Python full offline suite and real Chromium synthetic
  1,000-hour report smoke tests passed on the pre-launcher code
  (`45053604295`). **The final CI run including the launcher
  installer must also pass before tagging this release.**
- Supervised 90 s CH1 real hardware experiments, pause/manual/resume,
  CV/CC estimate change through a 15 Ω current-limited load and moving
  profile cursor were observed and documented in
  `docs/HARDWARE_ACCEPTANCE_v13_6.md` and `docs/SESSION_STATE.md`.
- The real 17:56 measurement CSV contained 495 readbacks, zero failures
  and a post-restoration `physical_output_checked` near 10.986 V.
  Snapshot and final verification confirmed restoration to the
  instrument's **original programmed 11.000 V / 3.530 A / output ON**.
  This is not equivalent to a safe output-OFF shutdown.
- Offline regression of the corrected final-state GUI display replays
  ON restoration, OFF restoration, failed verification and stale
  profile measurements without making additional PSU queries.
- Screenshot PNGs provided during development are not currently
  committed to GitHub. No broken README screenshot references.

## Known limits

Do not treat a logged `LOCAL` command as a readback of local mode;
user physically confirmed LOCAL in a previous supervised session.
Do not assume physical safety or output-OFF after abnormal interruption:
restore returns the originally programmed state, potentially ON. A
power cut, PSU/network fault or real disk exhaustion can prevent
safe restoration. The current-limit state is inferred, not continuous
instrument mode telemetry. Multi-day unattended operation and real
power-loss recovery were not physically validated.

`main` and version tag details are recorded in GitHub once published.
