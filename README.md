# CPX400DP PSU Control

**Current development baseline: v13.6 on `dev` (offline-tested, hardware validation pending).**  
**Stable baseline: v13.5 merged to `main` (hardware validation completed 2026-11-15).**

Linux/Kubuntu Python control application for Aim-TTi CPX400DP PSU, supporting CSV profile execution, pause/manual/resume, Ethernet discovery, interactive reports and standalone manual control.

## Version status

| Version | Branch / evidence | Status |
| --- | --- | --- |
| v13.3 | `docs/RELEASE_v13_3.md` | Historical imported baseline |
| v13.4 | Subsequent changes on `dev`; `docs/RELEASE_v13_4.md` | Historical development milestone: output-state buttons, coloured indicators, confirmation-free Resume |
| v13.5 | Merged into `main`, PR #1 / `7d5b393`; historical `docs/RELEASE_v13_5.md` | Hardware acceptance Stages 1–3 passed (see session state); latest pre-merge CI passed |
| v13.6 | `dev`; `docs/SESSION_STATE.md` | In development: lazy long-duration schedule, adaptive preview/report axes, last-observed CC/CV event indicators; offline-tested, **not hardware validated** |

Version labels do not establish a Git tag by themselves. v13.5 hardware tests and source evidence are documented in `docs/SESSION_STATE.md`. The v13.5 annotated tag has not been independently confirmed. The current v13.6 code has passed GitHub Actions offline tests, but **has not been tested on hardware**.

## Documentation to read first

- [Engineering handover](docs/PROJECT_HANDOVER.md): architecture, protocol, safety invariants, decisions, historical evidence
- [Session state](docs/SESSION_STATE.md): current development status, validation gaps and next steps
- [v13.5 historical notes](docs/RELEASE_v13_5.md): manual-control behaviour at that milestone
- [v13.4 historical notes](docs/RELEASE_v13_4.md), [v13.3 historical notes](docs/RELEASE_v13_3.md)

## Layout

- `scripts/` — application and SCPI modules
- `profiles/` — reusable legacy and waveform-only CSV profiles
- `profiles/negative_tests/` — **deliberately invalid fixtures; never run on hardware**
- `tests/` — offline regression suite
- `docs/` — operating instructions, handover, session state and release history
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

Manual voltage/current spinboxes and displayed live V/A values show two decimal places. Internally stored precision, SCPI payloads, and logged measurements are not rounded by this display-only change.

## v13.6 networking — first-use connection test

In Profile Runner, use **Test connection** before running a profile. The test
identifies the CPX400DP with read-only `*IDN?`, displays the verified host
and network interface, and closes its temporary TCP socket; **no output
commands, experiment start or PSU network changes occur**.

If the test reports an unconfigured physical Ethernet adapter (for example,
a Dell D6000 dock), **Prepare adapter…** offers an **optional, confirmed**
one-time automatic link-local IPv4 profile using NetworkManager (`nmcli`).
NetworkManager/Polkit may require desktop authorisation. Setup is refused when
the selected interface already has an IPv4 address or an active NetworkManager
connection. The application does not automatically reconfigure existing
Wi-Fi, other instrument ports, or PSU network parameters. In a managed
network, DHCP and read-only discovery remain the default.

For separate directly connected instruments with overlapping `169.254/16`
ranges, discovery binds TCP and multicast traffic to the selected adapter
and a local source address on that adapter. After a successful test, Profile
Runner and Manual Control reuse the discovered IP/interface fields, but
every actual run still makes a fresh verified control connection.

A PSU that was recently powered on may require around 30 seconds to obtain
its Auto-IP address. A second **Test connection** may then succeed without
configuring static addresses. If several instruments match, specify the
intended IP and network adapter rather than using an arbitrary first match.

The CSV chooser now remembers the last selected folder across launches.
On first use, it starts at `profiles/`, rather than `~/Downloads`.

**Scope:** these networking changes are **offline-tested only**. They
require real dock/PSU and NetworkManager validation before release. More
development items are tracked in [the backlog](docs/BACKLOG.md).

## v13.6 development notes

- The scheduler validates and streams a synthetic 1,000-hour profile with 50 ms update intervals without allocating every tick in advance. This does **not** validate 41-day unattended execution.
- Offline preview and report time axes adapt to seconds, minutes, hours or days. The report JavaScript avoids large argument-list spreads and retains local extrema in the displayed viewport. However, the report generator still reads full CSV logs into memory; processing truly massive recordings is **not yet solved**.
- Manual Control displays `CV`, `CC`, `UNREG` or `FAULT` as **last observed status events**, or UNKNOWN. CPX400DP `LSR1?`/`LSR2?` registers are **read-and-clear event registers**, not live regulation-mode readbacks. These labels are not guaranteed real-time mode information. Standalone Manual Control and paused-profile Manual Control use their existing single socket owners.
- v13.6 is development-only; no hardware safety or long-term reliability guarantee.

## Git and safety

Only version-control scripts, profiles, tests and documentation. `reports/` and large scope CSVs are excluded. Keep secrets and local connection details out of commits.

**This is laboratory automation, not a hardware safety interlock.** A failed connection may leave outputs at their last settings. Preserve the verified restoration and `LOCAL`-last behaviour when making changes; consult the handover.
