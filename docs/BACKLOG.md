# CPX400DP development backlog

**Updated:** 2026-11-17. **Branch:** `dev`. **Stable baseline:** v13.5 on `main`.

This file separates planned enhancements from implemented work. No entry below
is evidence of hardware validation. Priorities may be reordered only with
explicit agreement; keep existing safety/restore behaviour unchanged.

## Current focus: verified PSU address persistence (v13.6)

- [x] **Source implemented:** GUI restores its last successfully verified
  PSU IPv4 address and available interface from per-user QSettings on
  startup, with no automatic network probe. Only a successful read-only
  Test connection overwrites those saved values. Failed/ambiguous tests
  and unverified manual typing do not overwrite them.
  Offline structural regression added; CI and physical GUI acceptance
  to be recorded separately.
- [x] **Hardware GUI acceptance PASS (2026-11-17):** user verified
  that both previously tested PSU address and interface are restored
  after fully closing and reopening the GUI on Kubuntu. Read-only
  Test connection had identified `192.168.71.2` via D6000
  `enx0c3796303396`. No output-control test implied. Offline
  regression workflow run 44166633012 completed successfully.
- [x] **Dedicated static bench networks user-validated:** Rigol
  `192.168.70.2` on built-in NIC `192.168.70.1`;
  PSU `192.168.71.2` on D6000 `192.168.71.1`.
  Both saved NetworkManager profiles reactivated after user-confirmed
  Kubuntu reboot; both sourced pings succeeded, Wi-Fi default retained;
  PSU GUI Test connection and Rigol capture GUI both passed.
  No further Rigol capture work requested.
- [ ] **Follow-up:** if no longer needed, retire/clarify the legacy
  link-local Prepare adapter and overlapping 169.254/16 persistence
  diagnostics without changing stable device control functionality.

## Historical priority: reliable network discovery and guided setup (v13.6)

- [x] **Documented two-instrument persistent networking proposal:**
  [NETWORK_PERSISTENCE_PLAN.md](NETWORK_PERSISTENCE_PLAN.md) records
  Rigol's saved `Wired connection 2` profile, D6000 externally
  configured address, proposed narrow per-host routes, a scoped new
  D6000 NetworkManager profile, backups, rollback and acceptance.
  **Review-only:** no OS configuration change executed.
- [ ] **User-approved profile migration:** after explicit approval,
  inventory existing UUIDs and implement/validate the plan with
  both instruments powered on; preserve Wi-Fi and test reconnects.


- [x] **Observe inactive Ethernet links in persistence report:** include
  Ethernet-style interfaces from the address snapshot even if currently
  missing an active link-local route; distinguish a missing route from
  a missing interface. Mock regression covers an absent Rigol route.
- [ ] **Validate actual saved NM profiles and propose approved persistence:**
  initial report showed only D6000 `169.254.51.8/16` and
  `connected (externally)`; need both powered-on instrument reports
  to design a safe two-link setup.


- [x] **Read-only persistence preflight in the GUI:** new **Assess persistence**
  worker checks current IPv4 routes, addresses, NetworkManager state
  and saved profile fields, warning about externally configured docks
  and unsaved /32 host routes. It never changes host networking or
  opens a PSU connection. Mock tests added; hardware test pending.
- [ ] **Persistent-profile proposal and opt-in application:** use preflight
  evidence to design a safe, reversible setup for PSU dock and Rigol
  without breaking Wi-Fi. Explicit approval required for actual changes.


- [x] **Defer independent DSRemote screen-thread fault** per user direction.
  DSRemote live display worked with PSU GUI open, including Wave Inspector,
  then stopped with `screen_thread.cpp line 783`; prior same error occurred
  with PSU GUI closed. Separate two-channel Rigol RAW capture also passed.
  Resume only if needed for stable simultaneous operation.
- [x] **Read-only effective route inspection in PSU Network settings:**
  when a PSU IPv4 is entered, `Inspect routes` now shows Linux's actual
  interface and source IP selected for that host and flags a mismatch with
  the chosen adapter. Adds no routes and no PSU commands. Mock tests added;
  pending hardware GUI validation.
- [x] **Explain blank IP more clearly:** CSV address first then auto-discovery.


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
- [x] **Declutter Profile Runner network controls (hardware/UI-tested):** replace
  inline PSU IP, Interface, Test connection and Prepare adapter with a
  single **Network settings…** button. Its separate nonmodal dialog has
  readable, untruncated IP/interface controls, read-only identity test,
  diagnostic messages, and opt-in NetworkManager adapter setup. No PSU
  discovery occurs on opening the dialog. The runner/Manual Control
  continue to read the same underlying values; GUI structural tests pass.
  **Hardware/UI acceptance PASS (2026-11-16):** GUI opened correctly on
  Kubuntu after PyQt5 QDialog import fix. User confirmed layout is fine;
  blank IP auto-discovered live PSU 169.254.51.7 via D6000 and
  auto-populated the verified address. No profile run was needed.
- [x] **Profile Runner toolbar layout (offline-tested):** moved
  **Network settings…** immediately to the right of the Profile
  duration field, removing the dedicated row and freeing vertical
  space. Existing dialog/connection behaviour unchanged.
  User visual acceptance of the new placement is still pending.
- [x] **Remove preview HOLD messaging altogether:** per user request,
  removed the HOLD and OFF-throughout warning text and its dedicated
  informational label from the Profile Runner toolbar. No output
  enable state, CSV interpretation, snapshot or restoration logic
  changed. Existing GUI status and console report profile errors.
- [x] **Read-only route-conflict audit (offline-tested):** Network
  settings now has **Inspect routes**, which checks OS IPv4 routes for
  overlapping subnets on separate interfaces, ignores /32 host-route
  exceptions and only displays findings. No route, address or
  NetworkManager changes occur.
- [x] **Read-only inspection limitation documented:** the user saw no
  overlapping routes with Rigol OFF, then repeated the check after
  powering it ON. Network inspection now warns that the result applies
  only to currently installed routes; it is not a proof of persistence.
- [x] **Conservative setup safety gate (offline-tested):** refuse to
  auto-add a link-local NetworkManager profile when a different active
  adapter already has an overlapping non-host route. This prevents
  silent reintroduction of the proven Rigol/PSU route collision.
- [ ] **User-approved persistent networking:** inspect existing
  NetworkManager profiles and routes, propose a safe configuration for
  directly connected instruments (including the externally configured
  D6000 dock), and explicitly preserve Rigol, Wi-Fi and other
  active connections. A read-only overlap audit is complete; migration
  and persistent routing remain planned and NOT hardware-tested.
- [ ] **Usability polish:** consider showing `Automatic discovery` explicitly
  when the PSU IP field is blank; the current auto-population on successful
  discovery is working and hardware-verified.
- [x] **Separate Rigol capture app: first independent waveform retrieval
  succeeded:** CH2 576/576 and CH4 856/856 acquired through automatic
  system route, no retrieval errors reported; export decimation 500
  saved only 2 rows per channel. Confirms basic Ethernet waveform
  acquisition, not continuous/high-volume transfer reliability.
- [x] **Independent moderate capture:** CH2 and CH4 each retrieved
  6,000/6,000 points, in five 1,200-point RAW blocks; both full-resolution
  exports succeeded. Separate earlier CH4 1200-request/128-response remains
  unexplained, but DSRemote analysis is deferred.
- [ ] **Rigol DSRemote waveform-read fault after successful connect:**
  after restoring the correct /32 host route, DSRemote established a
  session and displayed waveforms briefly, then failed at
  `screen_thread.cpp line 783`. Distinguish this from the already
  fixed initial socket connection/routing failure. Scope front panel
  remains normal; PSU GUI not required for reproduction. Independently
  compare single-shot acquisition via the existing Rigol tool.
- [ ] **Rigol DSRemote independent display fault:** user observed DSRemote
  display corruption/non-updating waveform after adjusting horizontal
  timebase, and later **reproduced the problem with the PSU GUI fully
  closed**. This rules out any conclusion that the PSU GUI must be open
  to cause the fault. Diagnose DSRemote waveform acquisition/rendering
  independently (verify scope front-panel state, network route,
  screenshots/scope acquisition state and DSRemote reconnection).
  Reproduction with the PSU GUI closed is evidence against a necessary
  PSU-GUI interaction but does not establish root cause.
- [ ] **Coexistence endurance:** confirm both instruments remain stable
  after persistent networking/reboot. Correct interface-specific
  routes MUST remain in place.
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

## Long-duration experiments, offline hardening and release preparation

- [x] **Release-candidate plan and minimal bench checklist:** documents
  RELEASE_CANDIDATE_v13_6.md and HARDWARE_ACCEPTANCE_v13_6.md.
  No main merge or release tag without explicit user approval.
- [x] **Screenshot-friendly fixture profiles:** 90 s dual-channel
  OFF-output preview, and a separate 90 s current-limited
  CH1-only live demo requiring a suitable resistive load.
- [ ] **Final supervised hardware acceptance:** one short 90 s live
  demo with programmed state restoration/LOCAL confirmation, optional
  pause/manual/resume. Screenshot capture as part of this run.
- [ ] **Final release decision:** audit dev changes, review evidence,
  obtain approval to merge dev into main and tag v13.6.

## Historical and remaining long-duration items

- [x] **Runtime storage warning (source implemented):** add read-only
  30-second-poll free-space check during runner heartbeat; when output
  filesystem reaches 512 MiB reserve, issue console warnings with
  five-minute repeat limit. No automatic stop, PSU commands, file
  deletion or override of restoration logic. See RECORDING_RECOVERY.md.
  Offline regressions added; distinguish from disk-full write recovery.
- [x] **Read-only interrupted recording audit (source implemented):**
  stream over existing measurement CSV and report observed readbacks,
  final-state/LOCAL events, interruption/fault, last recorded time
  and synthetic-data marker. Audit never connects to PSU, changes
  outputs or deletes files; logs are not physical safety proof.
- [x] **Sparse long-duration preview examples:** add 24h (5 keyframes),
  7d (8), 1000h (11) to profiles/examples, all commanding outputs OFF.
  Tests validate profile parsing and safe-off keyframes. Synthetic
  approximately 120k-row mock 1000h CSV and 50ms peak supplied in a
  downloadable ZIP (not committed due to size).
- [x] **CSV write/flush failure containment (offline-tested):** active
  logging failures abort into configured cleanup; cleanup logging
  failures do not stop final restoration/LOCAL attempts; recording
  exits nonzero and auto-report is skipped if CSV is incomplete.
  Fault injection covers active writes, final-state logging and
  post-LOCAL summary logging, with LOCAL last and restoration attempted.
  Still not a physical disk-full, crash or PSU-power-loss validation.
- [x] **Opt-in archive retention (offline):** new
  scripts/cpx400dp_archive.py packs raw measurement CSV, matching
  report HTML, sidecar chunk folder and console log, generates
  checksum manifest, verifies ZIP and never deletes/overwrites
  original recordings. No scheduled deletion or automatic cleanup
  policy. Multi-day backup strategy remains an operator decision.


- [x] **Advisory pre-run disk-capacity forecast (source implemented):**
  estimate logging budget using profile duration, setpoint and readback
  intervals and channel count, plus a 512 MiB reserve; warn before opening
  the measurement CSV or instrument connection if free capacity is lower.
  This is read-only and never prevents a run; no runtime disk monitoring,
  guaranteed space reservation, report-size prediction or hardware
  endurance claims. Offline unit regression added; final CI pending.


- [x] Lazy scheduler and bounded-gap validation for a synthetic
  1,000-hour/50 ms profile (offline tested, **not a 41-day instrument run**).
- [x] Dynamic preview/report time axes (seconds/minutes/hours/days);
  browser-side per-pixel extrema preservation for visible windows.
- [x] **Large-log reporting source implemented (offline):** CSV files at
  least 8 MiB now use the new two-pass streaming report generator.
  Small logs retain the legacy self-contained HTML. The new HTML
  includes fixed-size first/last/min/max overview buckets, a local
  companion _report_data directory, per-channel 4096-record JS chunks,
  time-range indexing, demand-loading and six-chunk browser cache.
  Step-profile traces, output/pause/ramp indicators and direct
  time-window navigation are included. See REPORT_STREAMING.md.
  Full-suite CI and desktop-browser acceptance recorded separately.
  This does NOT make report storage or runtime disk monitoring bounded.
- [x] **Real-browser synthetic acceptance (CI):** Chromium Playwright
  opens file:// streaming report, navigates directly to an isolated
  synthetic 50 ms transient near 1000h, loads detail JS files,
  checks plotted peak, cursor operation and console errors.
  CI uploads a short-lived synthetic screenshot artifact. This is
  synthetic data only; operator screenshots and real hardware
  endurance remain separate acceptance gates.
- [ ] **Large-report robustness and retention:** design automatic old-data
  cleanup/retention, ensure complete report+data-folder archival,
  and consider storing compact indexed data in fewer files for
  many-day high-rate readbacks.
- [x] **50 ms zoom smoke-tested in real headless browser:** synthetic
  1000-hour file/report with 50 ms peak, local detail loading and
  viewport axis scaling; real measurement data and human screenshot
  review remain optional.
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
