"""Read-only persistence preflight for direct-connected bench instruments.

Diagnoses current IPv4 addresses and NetworkManager ownership; never fixes,
activates, deletes, or creates a route/profile. This is a snapshot only.
"""
import ipaddress
import json
import subprocess


def _read(args, runner):
    return runner(args, capture_output=True, text=True, check=True,
                  timeout=5).stdout.strip()


def persistence_preflight(psu_host=None, *, runner=subprocess.run):
    """Explain active overlapping link-local routes and likely persistence gaps.

    No conclusion from current route state proves a reboot outcome.
    """
    routes = json.loads(_read(['ip', '-j', '-4', 'route', 'show', 'table', 'main'], runner))
    addresses = json.loads(_read(['ip', '-j', '-4', 'addr', 'show'], runner))
    links = {}
    for item in addresses:
        nic = item.get('ifname')
        if nic:
            ips = [a.get('local') + '/' + str(a.get('prefixlen'))
                   for a in item.get('addr_info', [])
                   if a.get('family') == 'inet' and a.get('local')
                   and a.get('prefixlen') is not None]
            links[nic] = ips
    direct = set()
    host_routes = []
    for route in routes:
        destination = route.get('dst', '')
        nic = route.get('dev')
        if not destination or not nic:
            continue
        try:
            subnet = ipaddress.ip_network(destination, strict=False)
        except ValueError:
            continue
        if subnet.version != 4 or not subnet.overlaps(ipaddress.ip_network('169.254.0.0/16')):
            continue
        direct.add(nic)
        if subnet.prefixlen == 32:
            host_routes.append((str(subnet.network_address), nic))
    lines = ['READ-ONLY NETWORK PERSISTENCE PREFLIGHT',
             'Snapshot only: a successful current route does not prove reboot persistence.',
             'No routes, profiles, addresses or instrument settings have been changed.', '']
    if len(direct) > 1:
        lines.append('Multiple interfaces carry overlapping IPv4 link-local destinations: '
                     + ', '.join(sorted(direct)) + '.')
        lines.append('Host-specific /32 routes may be needed to resolve ambiguous instrument traffic.')
    elif direct:
        lines.append('One currently observed link-local interface: ' + next(iter(direct)) + '.')
    else:
        lines.append('No active IPv4 link-local routes observed; power on and connect instruments.')
    lines.append('')
    for nic in sorted(direct):
        lines.append('Adapter ' + nic + ':')
        lines.append('  Active IPv4: ' + (', '.join(links.get(nic, [])) or '(none)'))
        try:
            state = _read(['nmcli', '-g', 'GENERAL.STATE', 'device', 'show', nic], runner)
            profile = _read(['nmcli', '-g', 'GENERAL.CONNECTION',
                             'device', 'show', nic], runner)
        except (OSError, subprocess.SubprocessError) as exc:
            lines.append('  NetworkManager details unavailable: ' + str(exc))
            continue
        lines.append('  NetworkManager state: ' + (state or '(unknown)'))
        lines.append('  NetworkManager connection: ' + (profile or '(none)'))
        if 'externally' in state.lower():
            lines.append('  WARNING: device is connected externally; current address '
                         'must not be assumed to survive a reconnect or reboot.')
            continue
        if not profile or profile in ('--', '(none)'):
            lines.append('  WARNING: no active NetworkManager profile was identified.')
            continue
        try:
            method = _read(['nmcli', '-g', 'ipv4.method',
                            'connection', 'show', profile], runner)
            configured = _read(['nmcli', '-g', 'ipv4.addresses',
                                'connection', 'show', profile], runner)
            saved_routes = _read(['nmcli', '-g', 'ipv4.routes',
                                  'connection', 'show', profile], runner)
            autoconnect = _read(['nmcli', '-g', 'connection.autoconnect',
                                 'connection', 'show', profile], runner)
        except (OSError, subprocess.SubprocessError) as exc:
            lines.append('  Cannot verify saved profile settings: ' + str(exc))
            continue
        lines.append('  Saved IPv4 method: ' + (method or '(unknown)'))
        lines.append('  Saved IPv4 address: ' + (configured or '(none explicitly set)'))
        lines.append('  Autoconnect: ' + (autoconnect or '(unknown)'))
        if autoconnect.lower() not in ('yes', 'true'):
            lines.append('  WARNING: autoconnect is not confirmed enabled.')
        for host, interface in host_routes:
            if interface == nic:
                if (host + '/32' in saved_routes or
                        any(token.split('/')[0] == host for token in saved_routes.replace(',', ' ').split())):
                    lines.append(f'  Host route {host}/32 appears in saved NetworkManager ipv4.routes.')
                else:
                    lines.append(f'  WARNING: active host route {host}/32 has no matching '
                                 'saved NetworkManager ipv4.routes entry in this profile.')
                    lines.append('  It may be temporary or supplied by another mechanism.')
        lines.append('')
    if psu_host:
        try:
            host = str(ipaddress.IPv4Address(psu_host))
        except ValueError:
            lines.append('PSU route: invalid IPv4 address provided.')
        else:
            try:
                result = json.loads(_read(['ip', '-j', '-4', 'route', 'get', host], runner))
                route = result[0] if isinstance(result, list) and result else {}
                lines.append('Current effective PSU route: ' + host + ' via ' +
                             str(route.get('dev', '(unknown)')) + ', source ' +
                             str(route.get('prefsrc', route.get('src', '(unknown)'))) + '.')
            except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
                lines.append('Could not inspect current PSU route: ' + str(exc))
    lines.extend(['', 'NEXT STEP: review the actual saved profile configuration '
                  'before proposing changes. Do not use Prepare adapter on an '
                  'existing externally configured dock or overlapping network.',
                  'Any persistent configuration must be separately approved '
                  'and tested with both instruments powered on.'])
    return '\n'.join(lines)
