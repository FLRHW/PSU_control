"""Read-only interface diagnostics and opt-in NetworkManager link-local setup.

Never change PSU settings, routes, or active general-purpose interfaces. The
optional one-time profile creation requires explicit UI confirmation and normal
NetworkManager/Polkit authorization. No sudo, shell, or elevated daemon.
"""
import ipaddress
import json
import re
from pathlib import Path
import subprocess

PROFILE_PREFIX = 'CPX400DP-direct-'


def adapter_details():
    """All UP Ethernet-class interfaces, INCLUDING those without IPv4.

    Prefer iproute2, already used by discovery. Do not confuse a USB dock
    (often named enx...) with a special case.
    """
    proc = subprocess.run(['ip', '-j', 'addr', 'show', 'up'],
                          capture_output=True, text=True, check=True, timeout=4)
    result = []
    for item in json.loads(proc.stdout):
        name = item.get('ifname', '')
        if name == 'lo' or item.get('link_type') != 'ether':
            continue
        if item.get('operstate') == 'DOWN':
            continue
        ipv4 = [a.get('local') for a in item.get('addr_info', [])
                if a.get('family') == 'inet' and a.get('local')]
        sysnet = Path('/sys/class/net') / name
        wireless = (sysnet / 'wireless').exists()
        physical = (sysnet / 'device').exists()
        result.append({'name': name, 'ipv4': ipv4,
                       'carrier': 'LOWER_UP' in item.get('flags', []),
                       'mac': item.get('address', ''),
                       'kind': 'wifi' if wireless else 'ethernet' if physical else 'virtual'})
    return result


def is_setup_candidate(item):
    """A connected Ethernet adapter with no IPv4 address."""
    return bool(item.get('kind') == 'ethernet' and
                item.get('carrier') and not item.get('ipv4') and
                re.fullmatch(r'[a-zA-Z0-9_.-]{1,15}', item.get('name', '')))


def setup_ethernet_link_local(interface, *, runner=subprocess.run):
    """Create and activate ONE dedicated NM profile, only on a bare adapter.

    Permission is handled by NetworkManager/Polkit. A failure is returned
    rather than triggering sudo, silently changing any other network, or
    retrying automatically.
    """
    matches = [item for item in adapter_details() if item['name'] == interface]
    if len(matches) != 1 or not is_setup_candidate(matches[0]):
        raise ValueError('Adapter is not a connected, unconfigured Ethernet port; no changes made')
    # Do not replace an already active connection profile (which may be used
    # for VLAN, VPN, router management or an unrelated instrument).
    active = runner(['nmcli', '-g', 'GENERAL.CONNECTION', 'device', 'show', interface],
                    capture_output=True, text=True, timeout=6, check=True).stdout.strip()
    if active and active not in ('--', '(none)'):
        raise ValueError('Adapter has an active NetworkManager profile; no changes made')
    # A new link-local /16 would overlap an existing direct instrument link.
    # Refuse setup rather than silently reroute another instrument.
    audit = runner(['ip', '-j', '-4', 'route', 'show', 'table', 'main'],
                   capture_output=True, text=True, timeout=4, check=True)
    for entry in json.loads(audit.stdout):
        dest = entry.get('dst', '')
        other = entry.get('dev')
        if not dest or not other or other == interface:
            continue
        try:
            subnet = ipaddress.ip_network(dest, strict=False)
        except ValueError:
            continue
        if subnet.prefixlen < 32 and subnet.overlaps(
                ipaddress.ip_network('169.254.0.0/16')):
            raise ValueError(
                f'Existing link-local network {subnet} on {other}; '
                'automatic adapter setup would risk disconnecting another '
                'instrument. No changes made. A multi-link configuration '
                'requires reviewed per-host routes.')
    profile = PROFILE_PREFIX + interface
    # This can prompt the user via Polkit; it does not configure the PSU.
    runner(['nmcli', 'connection', 'add', 'type', 'ethernet',
            'ifname', interface, 'con-name', profile,
            'ipv4.method', 'link-local', 'ipv6.method', 'disabled',
            'connection.autoconnect', 'yes'],
           capture_output=True, text=True, timeout=20, check=True)
    try:
        runner(['nmcli', 'connection', 'up', profile, 'ifname', interface],
               capture_output=True, text=True, timeout=35, check=True)
    except (OSError, subprocess.SubprocessError):
        # Avoid leaving an unverified auto-connect profile after failure.
        try:
            runner(['nmcli', 'connection', 'delete', profile],
                   capture_output=True, text=True, timeout=15, check=True)
        except (OSError, subprocess.SubprocessError):
            pass
        raise
    return profile


def diagnose_connection(host=None, interface=None):
    """Read-only identification; return a GUI-friendly structured result.

    A CPX400DP is identified ONLY by its *IDN? response, never by a ping,
    MAC address, ARP entry or the mere presence of an Ethernet cable.
    """
    from cpx400dp_discovery import discover
    devices = adapter_details()
    candidates = [item for item in devices if is_setup_candidate(item)]
    if interface:
        selected = [item for item in devices if item['name'] == interface]
        if not selected:
            return {'status': 'missing', 'message': f'Network adapter {interface} is not connected.',
                    'matches': [], 'setup': []}
        if not selected[0]['ipv4']:
            return {'status': 'unconfigured',
                    'message': f'Network adapter {interface} has no IPv4 address. '
                               'Use Prepare adapter to enable automatic link-local addressing.',
                    'matches': [], 'setup': [interface] if is_setup_candidate(selected[0]) else []}
    try:
        found = discover(last_host=host, preferred_interface=interface, all_matches=True)
    except (OSError, ValueError, ConnectionError) as exc:
        return {'status': 'error', 'message': str(exc), 'matches': [],
                'setup': [item['name'] for item in candidates]}
    if len(found) == 1:
        address, nic, identity = found[0]
        return {'status': 'found', 'message': f'{identity} at {address}, using {nic}',
                'matches': found, 'setup': []}
    if len(found) > 1:
        return {'status': 'multiple',
                'message': 'Multiple CPX400DP connections detected; select an IP and adapter '
                           'before starting a profile.',
                'matches': found, 'setup': []}
    if candidates:
        return {'status': 'unconfigured',
                'message': 'No CPX400DP identified. One or more connected Ethernet adapters '
                           'have no IPv4 address; these may be direct instrument links.',
                'matches': [], 'setup': [item['name'] for item in candidates]}
    return {'status': 'not_found',
            'message': 'No CPX400DP responded to read-only identification. Check PSU power, '
                       'cables and whether Auto-IP startup has finished (approximately 30 s).',
            'matches': [], 'setup': []}


def overlapping_ipv4_routes(*, runner=subprocess.run):
    """Read-only route audit for separate physical instrument networks.

    Returns distinct (subnet, interface A, interface B) collisions.
    Host-specific /32 exceptions are not collisions. No routing or
    NetworkManager settings are modified.
    """
    proc = runner(['ip', '-j', '-4', 'route', 'show', 'table', 'main'],
                  capture_output=True, text=True, check=True, timeout=4)
    routes = []
    for entry in json.loads(proc.stdout):
        destination = entry.get('dst')
        device = entry.get('dev')
        if not destination or destination == 'default' or not device:
            continue
        try:
            network = ipaddress.ip_network(destination, strict=False)
        except ValueError:
            continue
        # /32 routes are deliberate instrument-specific exceptions.
        if network.prefixlen == 32:
            continue
        routes.append((network, device))
    collisions = set()
    for index, (first, nic1) in enumerate(routes):
        for second, nic2 in routes[index + 1:]:
            if nic1 != nic2 and first.overlaps(second):
                collisions.add((str(first), nic1, str(second), nic2))
    return sorted(collisions)



def instrument_route_summary(host, expected_interface=None, *, runner=subprocess.run):
    """Read-only Linux effective route for a known IPv4 instrument address.

    The connected-route table alone does not show which of two overlapping
    link-local routes wins. A host-specific /32 may resolve that ambiguity.
    Never run route 'replace', NetworkManager or a socket probe here.
    """
    try:
        address = ipaddress.IPv4Address(host)
    except (ValueError, ipaddress.AddressValueError):
        return 'Cannot inspect instrument route: enter a valid PSU IPv4 address.'
    proc = runner(['ip', '-j', '-4', 'route', 'get', str(address)],
                  capture_output=True, text=True, check=True, timeout=4)
    entries = json.loads(proc.stdout)
    if not isinstance(entries, list) or not entries:
        return f'No effective IPv4 route reported for {address}.'
    route = entries[0]
    nic = route.get('dev') or 'unknown interface'
    source = route.get('prefsrc') or route.get('src') or 'unknown source'
    message = f'Effective route to PSU {address}: {nic} (source {source}).'
    if expected_interface and expected_interface != nic:
        message += (f' WARNING: selected adapter {expected_interface} is not '
                    'the normal system route. The application may bind its '
                    'own socket to the selected adapter, but other tools '
                    'using automatic routing can reach the wrong port.')
    return message


def network_route_summary(*, runner=subprocess.run):
    """Human-readable, diagnostic-only warning for overlapping IPv4 routes."""
    collisions = overlapping_ipv4_routes(runner=runner)
    if not collisions:
        return ('No overlapping IPv4 routes among the networks currently '
                'installed. This is a snapshot, not a permanent network '
                'health check. Routes can disappear when an instrument or '
                'dock link is down and reappear when it reconnects; repeat '
                'with all instruments and adapters connected.')
    details = '; '.join(
        f'{left} on {nic1} overlaps {right} on {nic2}'
        for left, nic1, right, nic2 in collisions)
    return ('Overlapping network routes detected: ' + details +
            '. Linux may send traffic for an instrument through the wrong '
            'Ethernet port. Existing host-specific routes can make the '
            'instruments usable, but automatic configuration should not '
            'change these routes without an explicit review.')
