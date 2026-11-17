# Two-instrument Ethernet persistence — proposed plan (NOT APPLIED)

## Preferred simplification (2026-11-17, NOT APPLIED)

The user requested a less complex, standard setup. NIC hardware identities
were confirmed read-only: built-in `enp3s0f1` MAC
`18:3d:2d:3c:93:6d`; D6000 `enx0c3796303396` MAC
`0c:37:96:30:33:96`. They are **host NIC MACs**, not instrument
MACs. A preferable durable approach, if accepted, is to move both
instruments to manual static IPv4 with two *different* /24 networks:

| Link | Host (proposal) | Instrument (proposal) |
| --- | --- | --- |
| Rigol | `192.168.70.1/24` | `192.168.70.2/24` |
| CPX400DP | `192.168.71.1/24` | `192.168.71.2/24` |

Instrument manuals document static IP support; first verify the selected
settings can be applied and recovered on each actual device. Configure
separate **MAC/interface-bound** NM connections with `never-default=yes`,
no gateway, autoconnect enabled; safely constrain/remove the old unbound
profile's autoconnect after backing up its UUID; keep Wi-Fi unchanged.
No host routes are required because these are non-overlapping networks.
Stage each device change in a recoverable order with independent link tests,
and explicitly approve any OS/instrument changes before running them.
The earlier Auto-IP + /32 recipe remains a fallback for instruments whose
IP cannot be changed, not the preferred design. All addresses above are
**proposals**, NOT observations, and **nothing has been configured**.

> **REVISED DIAGNOSIS — 2026-11-17: EARLIER COMMAND EXAMPLES ARE SUPERSEDED.**
>
> Saved profile `Wired connection 2` UUID `4158f5eb-2e6b-3274-8f74-bb2a48c41126`
> has no interface-name or Ethernet MAC binding and autoconnect=yes. It is
> **currently active on the D6000 PSU dock**, unexpectedly applying
> `169.254.10.1/16` to `enx0c3796303396`, while the Rigol NIC
> `enp3s0f1` has carrier but NM state disconnected and no IPv4.
> Both instrument destinations currently route through the dock.
> **DO NOT execute the old `nmcli connection modify "Wired connection 2"`
> example as written**: the generic profile must first be explicitly
> bound or otherwise prevented from roaming, with verified MAC identity,
> UUID-based backup and a safe rollback. This document is still a
> proposal and NO changes to the host have been applied.
>
> Updated design: establish **two distinct interface/MAC-bound Ethernet
> profiles**, one for the built-in Rigol interface (host
> `169.254.10.1/16`, Rigol destination `169.254.179.79/32`) and one
> for the D6000 (host `169.254.51.8/16`, PSU destination
> `169.254.51.7/32`); set never-default=yes and autoconnect=yes on
> each; remove ambiguity from the generic roaming autoconnect profile;
> preserve Wi-Fi and provide rollback by exact UUID. Check physical
> interface MACs, any duplicate profiles, and current instrument Auto-IP
> addresses before planning precise mutation/activation steps.
>
> **The subsequent 'Verified active topology' table is historical, NOT
> the current runtime state.** Current observed state is as described
> above; do not mistake the old Rigol profile association or dock host
> address for verified current values. After authorization, validate
> routes, read-only instrument identity, disconnect/reconnect, and reboot.
> Unchanged Auto-IP assignments are an assumption, not a guarantee.

**Status:** engineering proposal for explicit review, 2026-11-17.
**Branch:** `dev`; **host OS changes:** NONE.
**Scope:** Lenovo M75q / Kubuntu, direct Rigol DS1054Z and CPX400DP
through independent Ethernet NICs. Keep Wi-Fi and unrelated interfaces
untouched. This document is NOT a script; commands below are examples
and must not be executed as a batch.

## Verified active topology

| Instrument | Instrument IPv4 observed | Linux NIC | Host IPv4 now | NetworkManager |
| --- | --- | --- | --- | --- |
| Rigol DS1054Z | `169.254.179.79` | `enp3s0f1` | `169.254.10.1/16` | `Wired connection 2`; manual address saved; autoconnect=yes |
| CPX400DP | `169.254.51.7` | `enx0c3796303396` (D6000) | `169.254.51.8/16` | connected **externally**; no saved address confirmed |
| Wi-Fi | gateway `192.168.0.1` | `wlp4s0` | `192.168.0.252/24` | active home internet |

The two separate direct links both install a route to `169.254.0.0/16`.
This is ambiguous. The earlier kernel selected the D6000 interface even
for `169.254.179.79`, so DSRemote could not open. The temporary
`169.254.179.79/32` host route via `enp3s0f1` restored 4/4 pings
and connection. Link down/up may remove this *unsaved* route.

The first power-on preflight lists:
- Rigol `Wired connection 2`: method manual; saved `169.254.10.1/16`,
  autoconnect yes. No saved static host route appeared in the report.
- Dock: `100 (connected (externally))`; `169.254.51.8/16`;
  persistence unproven. No persistent profile should be assumed.
- Both `169.254/16` networks active.

## Preferred initial approach: preserved addresses + narrow per-host routes

1. Keep Rigol's working `Wired connection 2` NM profile and its saved
   `169.254.10.1/16` address. **After backing it up**, add a persistent
   destination-specific route `169.254.179.79/32` through that
   interface, no gateway. If the route already exists in the saved profile,
   do not duplicate it.
2. Create a **new, interface-bound** NetworkManager connection profile
   for the D6000's specific hardware NIC with **manual**
   `169.254.51.8/16`, IPv6 disabled for this isolated link,
   autoconnect enabled, **never-default=yes**, and a persistent
   destination-specific `169.254.51.7/32` route. Do NOT replace
   the Rigol, Wi-Fi or other active connections.
3. Set explicit metrics for the two broad connected link-local routes
   if desirable, but **never rely on metric alone** to distinguish
   two endpoints on different cables; the two /32 routes are what
   pin known instrument addresses to their intended ports.
4. After explicit approval and profile backups, activate only the new
   D6000 profile. This will likely interrupt the temporary PSU address
   briefly. Recheck both `ip -4 route get` results, both pings and
   read-only `*IDN?` replies. Also verify the default Wi-Fi route is
   still `wlp4s0`.
5. Disconnect/reconnect links and reboot **only after** the initial
   route checks are known-good, with the ability to roll back.
6. Inspect `nmcli -f NAME,UUID,TYPE,DEVICE connection show` before
   changes. A `connected (externally)` runtime connection is not
   proof of a saved NM profile, but a saved profile with the intended
   name may already exist. Do not overwrite a duplicate profile.

This plan assumes the scope and PSU **retain their presently observed
Auto-IP addresses**. If their link-local IPs change, the persistent
host routes become stale; re-discovery and a revised configuration
are needed. The USB dock can also be unplugged, change names, or
be used for another network. Binding to the verified adapter's
hardware identity and refusing to activate on ambiguity should
precede any automated migration.

## Example commands for review, NOT FOR EXECUTION YET

The following illustrate the intended NetworkManager operations
after confirming profile uniqueness, the actual adapter identity
and a suitable rollback; they deliberately **do not** include
`connection up` or deletions.

```bash
# Read-only baseline and inventory:
nmcli -f NAME,UUID,TYPE,DEVICE connection show
nmcli -f connection.id,connection.interface-name,connection.autoconnect,ipv4.method,ipv4.addresses,ipv4.routes,ipv4.never-default,ipv4.route-metric connection show "Wired connection 2"
ip -4 route get 169.254.179.79
ip -4 route get 169.254.51.7
ip -4 route

# Proposed permanent Rigol host route on saved existing profile:
# nmcli connection modify "Wired connection 2" +ipv4.routes "169.254.179.79/32"

# Proposed D6000 profile, only after checking no matching saved profile exists:
# nmcli connection add type ethernet ifname enx0c3796303396 con-name CPX400DP-direct-enx0c3796303396 \
#   ipv4.method manual ipv4.addresses 169.254.51.8/16 \
#   ipv4.never-default yes ipv6.method disabled connection.autoconnect yes
# nmcli connection modify CPX400DP-direct-enx0c3796303396 \
#   +ipv4.routes "169.254.51.7/32"
```

NetworkManager supports manual addresses, explicit host routes,
`ipv4.never-default` and `connection.autoconnect`. Route settings
in saved profiles should survive NetworkManager reconnection when
correctly applied, whereas manually entered `ip route` operations
do not themselves establish profile persistence. See
[NetworkManager settings reference](https://networkmanager.pages.freedesktop.org/NetworkManager/NetworkManager/nm-settings-nmcli.html).

## Safety, rollback, acceptance

- User approval is needed **before any OS changes**. Never run
  `nmcli connection add/modify/up/down/delete`, `ip addr` writes,
  or `ip route` writes simply to inspect routes.
- Before any approved changes, record connection UUIDs and full
  relevant profiles, active routes and interface addresses.
  Preserve the pre-existing `Wired connection 2` contents; use
  the UUID rather than a possibly non-unique display name.
- A failed D6000 activation should not delete an unrelated profile.
  Rollback restores the exact backed-up Rigol NM properties and
  removes **only the newly created** D6000 profile by its verified UUID.
  Avoid disconnecting Wi-Fi during rollback.
- Accept only if `169.254.179.79` goes via `enp3s0f1` with
  `169.254.10.1`, `169.254.51.7` via `enx0c3796303396`
  with `169.254.51.8`; both instruments respond to intended
  read-only identification, the default remains on Wi-Fi, and
  profiles survive relevant reconnects/reboot.
- If Auto-IP device addresses change, static host routes will
  require reconfiguration; no guarantee of indefinite stability
  is made. A non-overlapping fixed-IP instrument plan would require
  explicit device-side configuration and separate validation.
- The DSRemote intermittent `screen_thread.cpp line 783` waveform
  error is **deferred**: evidence suggests it is separate from the
  correctable initial route-selection problem.

## Implementation status

**Only this written proposal and the read-only GUI preflight are
implemented.** None of the described host configuration changes,
reboot tests, or multi-instrument persistence validations are
implemented or hardware-tested. `main` stays at stable v13.5.
