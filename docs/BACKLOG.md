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
- [ ] **Hardware-validate** dock-to-PSU link and verify read-only identity;
  confirm behaviour alongside Rigol directly connected via a different port.
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
