# CPX400DP development backlog

**Updated:** 2026-11-16. **Branch:** `dev`. **Stable baseline:** v13.5 on `main`.

This file separates planned enhancements from implemented work. No entry below
is evidence of hardware validation. Priorities may be reordered only with
explicit agreement; keep existing safety/restore behaviour unchanged.

## Active priority: reliable network discovery and guided setup (v13.6)

- [x] Find physical Ethernet interfaces even when an adapter (including a
  Dell D6000 dock) has carrier but no IPv4 address.
- [x] Explicitly bind link-local TCP and mDNS discovery to the selected adapter
  and a source address on that adapter, avoiding the usual overlapping
  169.254/16 source-address ambiguity.
- [x] Read-only **Test connection** in Profile Runner, with instrument identity
  from `*IDN?`, duplicate-device handling, clear diagnostics, and no competing
  runner/manual-control socket.
- [x] Opt-in **Prepare adapter** for a connected, physical, unconfigured Ethernet
  NIC using `nmcli` and NetworkManager/Polkit; refuse Wi-Fi, virtual NICs,
  adapters with IPv4 or any existing active NetworkManager profile. No
  automatic PSU IP configuration.
- [x] Reopen CSV chooser in last-used profile folder, else project `profiles/`
  directory, else home.
- [x] **Hardware-validate read-only** dock-to-PSU `*IDN?` identification
  (2026-11-16: THURLBY THANDAR, CPX400DP, serial 446696, fw 2.00-4.06;
  `169.254.51.7` via `enx0c3796303396`). This does not validate
  control/restore or a persistent NetworkManager profile.
- [x] Avoid *IDN? probe-then-reconnect for actual runner and standalone
  Manual Control; retain the exact successfully identified TCP connection.
  Offline regression tested; on-hardware verification still needed.
- [x] **Hardware-validated** retained-socket runner, standalone Manual Control
  connection/readout/disconnect, original-state snapshot and `LOCAL`-last
  on 2026-11-16. Two-channel 10.csv run exit 0, 178 good readbacks,
  both programmed final states verified and sampled outputs matched.
  This is short-run validation, not uptime/reboot proof.
- [x] **Short-run simultaneous coexistence:** user confirmed Rigol DSRemote
  continued updating during PSU read-only test and reported normal DSRemote
  operation after successful 10.csv run. Earlier rendering issues were not
  reproduced in this run.
- [ ] **Declutter Profile Runner network controls:** replace the current
  cramped inline PSU IP, Interface, Test connection and Prepare adapter
  controls (IP field currently clips the address in the GUI) with one
  **Network settings…** button. Open a separate, comfortably sized dialog
  containing the complete, untruncated IP/interface fields, read-only
  discovery and identity tests, connection status/errors, and opt-in
  NetworkManager setup/advanced options. The main runner should display
  only a compact connected/not connected summary if helpful, without
  wasting persistent toolbar space. Preserve the verified connection
  implementation, avoid any background discovery while idle, and keep
  network tests/configuration disabled when the runner or Manual Control
  owns the instrument. Add GUI layout/state regression tests before
  hardware acceptance.
- [ ] **Coexistence endurance:** confirm no intermittent rendering loss
  across longer operation and after persistent network setup/reboot.
  Correct instrument-specific routes MUST remain in place.
- [ ] Support persistent non-overlapping routes or explicitly managed
  host-specific routes for separate directly connected Auto-IP instruments.
  Protect existing working Rigol/Wi-Fi interfaces; get permission before OS
  changes. The user's temporary /32 Rigol route currently masks a real
  overlapping 169.254/16 route conflict.
- [ ] Confirm a new NetworkManager direct-connection profile survives reboot
  and avoids requiring Linux networking commands; check it never disrupts
  existing Wi-Fi, Rigol or other network services.
- [ ] Optionally add VXI-11 broadcast discovery when existing known-address,
  ARP and mDNS methods cannot locate the PSU; keep read-only authentication
  using `*IDN?`.
- [ ] Improve Linux desktop network setup error details, retries and recovery
  for unmanaged/unconfigured adapters; consider optional serial-number
  selection if multiple CPX400DPs share a network.
- [ ] Evaluate whether a supervised 30-second Auto-IP wait/retry improves
  first connection after PSU power-up, without blocking the GUI.

## Deferred: long-duration experiments and reporting

- [x] Lazy scheduler and bounded-gap validation for a synthetic
  1,000-hour/50 ms profile (offline tested, **not a 41-day instrument run**).
- [x] Dynamic preview/report time axes (seconds/minutes/hours/days);
  browser-side per-pixel extrema preservation for visible windows.
- [ ] Report generator still reads the entire CSV in memory and embeds all
  data arrays in HTML; implement streaming aggregation and bounded, indexed
  on-demand data retrieval for large measurements.
- [ ] Verify short-time-span zoom (including 50 ms events) on very long
  recordings without losing peaks, transitions or timing accuracy.
- [ ] Define log-retention, disk-space monitoring, resilience to abrupt host
  shutdown/USB/network errors and bounded report memory usage.
- [ ] Perform controlled multi-hour hardware endurance testing before
  considering multi-day unattended experiment claims.

## Deferred: regulation indicators and measurement fidelity

- [x] Source-level and offline tests for conservative **last observed**
  CV/CC/UNREG/FAULT read-and-clear `LSR` event indicators in both
  standalone and paused-profile Manual Control.
- [ ] Compare event labels to physical front-panel regulation changes with
  safe resistive loads; acknowledge that `LSR?` does **not** report a
  guaranteed instantaneous operating mode.
- [ ] If a continuous mode indication is required, verify whether the PSU
  offers a separate authoritative state query; do **not** infer live CC/CV
  solely from output voltage/current or event register zero responses.

## Release criteria

- Complete the chosen network-revision hardware tests, offline regressions and
  user acceptance. Preserve verified pause/manual/resume, restoration,
  single-socket ownership and `LOCAL`-last behaviour.
- Only promote `dev` to `main` after explicit user approval.
