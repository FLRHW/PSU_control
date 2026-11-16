#!/usr/bin/env python3
"""Linux interface-aware CPX400DP discovery; Python standard library only.

Probe is read-only (*IDN?), never modifies host routing or PSU output state.
We use SO_BINDTODEVICE on Linux to disambiguate competing 169.254/16 routes.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import time

PORT = 9221
CACHE = Path.home() / '.config' / 'cpx400dp' / 'last_psu.json'


def interfaces():
    """Return active Ethernet devices, including dock adapters without IPv4."""
    from cpx400dp_network_setup import adapter_details
    try:
        return {item['name']: item['ipv4'] for item in adapter_details()}
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise OSError('Cannot enumerate Ethernet interfaces using iproute2: ' + str(exc)) from exc


def arp_candidates():
    """Neighbour table is useful even when the normal route is wrong."""
    out = []
    try:
        with open('/proc/net/arp', encoding='ascii') as f:
            for line in list(f)[1:]:
                fields = line.split()
                if len(fields) >= 6 and fields[3] != '00:00:00:00:00:00':
                    try:
                        out.append((str(ipaddress.IPv4Address(fields[0])), fields[5]))
                    except ipaddress.AddressValueError:
                        pass
    except OSError:
        pass
    return out


def cache_read():
    try:
        data = json.loads(CACHE.read_text())
        return (str(ipaddress.IPv4Address(data['host'])), data['interface'])
    except (OSError, KeyError, TypeError, ValueError):
        return None


def cache_write(host, interface):
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        temp = CACHE.with_suffix('.tmp')
        temp.write_text(json.dumps({'host': host, 'interface': interface}) + '\n')
        os.replace(temp, CACHE)
    except OSError:
        pass  # Cache failure must never make a hardware run fail.


def connect_on(host, interface, timeout=0.65):
    """Bind the outgoing TCP socket to a specific Linux NIC (not just source IP)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        if interface:
            if not hasattr(socket, 'SO_BINDTODEVICE'):
                raise OSError('Interface binding requires Linux SO_BINDTODEVICE')
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE,
                            interface.encode('ascii') + b'\0')
        if interface and ipaddress.IPv4Address(host).is_link_local:
            # SO_BINDTODEVICE selects the NIC, but source selection can still
            # use another NIC's 169.254 address when subnets overlap.
            source = next((addr for addr in interfaces().get(interface, [])
                           if ipaddress.IPv4Address(addr).is_link_local), None)
            if source is None:
                raise OSError(f'Network adapter {interface} has no link-local IPv4 address; '
                              'use guided network setup')
            sock.bind((source, 0))
        sock.connect((host, PORT))
        return sock
    except Exception:
        sock.close()
        raise


def probe(host, interface, timeout=0.65):
    """Identify instrument on a short-lived read-only connection."""
    try:
        with connect_on(host, interface, timeout) as s:
            s.sendall(b'*IDN?\n')
            reply = bytearray()
            while len(reply) < 512 and b'\n' not in reply:
                block = s.recv(512)
                if not block:
                    break
                reply.extend(block)
            identity = bytes(reply).split(b'\n')[0].decode('ascii', 'replace').strip()
            # Match model explicitly: do not accept unrelated LXI instruments.
            if re.search(r'\bCPX400DP\b', identity, re.IGNORECASE):
                return identity
    except (OSError, ValueError):
        pass
    return None


def _dns_name(data, pos, depth=0):
    if depth > 10:
        raise ValueError('DNS compression recursion exceeded')
    labels = []
    while True:
        if pos >= len(data):
            raise ValueError('Truncated DNS name')
        size = data[pos]
        pos += 1
        if size & 0xc0 == 0xc0:
            if pos >= len(data):
                raise ValueError('Truncated DNS pointer')
            dest = ((size & 0x3f) << 8) | data[pos]
            pos += 1
            sub, _ = _dns_name(data, dest, depth + 1)
            labels.append(sub)
            break
        if size == 0:
            break
        if size > 63 or pos + size > len(data):
            raise ValueError('Invalid DNS name')
        labels.append(data[pos:pos + size].decode('utf-8', 'replace'))
        pos += size
    return '.'.join(labels), pos


def _dns_answers(packet):
    """Extract advertised IPv4 hosts from mDNS A responses; validate via *IDN?."""
    out = []
    try:
        if len(packet) < 12:
            return out
        qd, an, ns, ar = struct.unpack_from('!4H', packet, 4)
        pos = 12
        for _ in range(min(qd, 50)):
            _, pos = _dns_name(packet, pos)
            pos += 4
        for _ in range(min(an + ns + ar, 100)):
            _, pos = _dns_name(packet, pos)
            typ, klass, ttl, length = struct.unpack_from('!HHIH', packet, pos)
            pos += 10
            if pos + length > len(packet):
                break
            if typ == 1 and length == 4:
                out.append(socket.inet_ntoa(packet[pos:pos + 4]))
            pos += length
    except (ValueError, struct.error, IndexError):
        pass
    return out


def mdns_candidates(interface, timeout=0.5):
    """Multicast _lxi._tcp.local service query on one interface, no Avahi required.

    Some PSU firmware may not advertise; discovery has manual fallback.
    """
    service = b'\x04_lxi\x04_tcp\x05local\x00'
    # QU bit requests unicast reply to the ephemeral UDP source port.
    query = b'\0\0\0\0\0\x01\0\0\0\0\0\0' + service + struct.pack('!HH', 12, 0x8001)
    values = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            if interface:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE,
                             interface.encode('ascii') + b'\0')
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            s.sendto(query, ('224.0.0.251', 5353))
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    data, _ = s.recvfrom(8192)
                except socket.timeout:
                    break
                values.update(_dns_answers(data))
    except OSError:
        pass
    return sorted(values)


def discover(last_host=None, preferred_interface=None, *, mdns=True,
             timeout=0.65, all_matches=False):
    """Return [(host, iface, identity)] candidates, prioritizing cached ones.

    Never scan all 65,536 link-local addresses automatically. Broadcast discovery,
    past neighbour entries, and explicitly supplied IPs cover usual setups.
    """
    links = interfaces()
    if preferred_interface and preferred_interface not in links:
        raise ValueError(f'Network adapter {preferred_interface!r} is not active')
    if preferred_interface and not links[preferred_interface]:
        raise ValueError(f'Network adapter {preferred_interface!r} has no IPv4 address; '
                         'use guided network setup')
    saved = cache_read()
    neighbours = arp_candidates()
    pairs = []
    def add(host, iface):
        if iface in nics and (host, iface) not in pairs:
            pairs.append((host, iface))
    nics = [preferred_interface] if preferred_interface else [nic for nic, addresses in links.items() if addresses]
    # Explicit CSV/GUI address takes precedence over cached discovery state.
    if last_host:
        for nic in nics:
            add(str(ipaddress.IPv4Address(last_host)), nic)
    if saved:
        add(*saved)
    for addr, nic in neighbours:
        if nic in nics:
            add(addr, nic)
    found = []
    def scan_pairs():
        for host, nic in pairs:
            if preferred_interface and nic != preferred_interface:
                continue
            if any((h, n) == (host, nic) for h, n, _ in found):
                continue
            ident = probe(host, nic, timeout)
            if ident:
                found.append((host, nic, ident))
                if not all_matches:
                    cache_write(host, nic)
                    return True
        return False
    if scan_pairs():
        return found
    # Multicast is only necessary if the cache, configured IP and neighbours
    # failed. Avoid gratuitous extra UDP probes in ordinary runs.
    if not found and mdns:
        for nic in nics:
            for addr in mdns_candidates(nic):
                add(addr, nic)
        scan_pairs()
    if len(found) == 1:
        cache_write(found[0][0], found[0][1])
    return found


def connect_psu(last_host, preferred_interface=None, *, discover_enabled=True):
    """Find and open the SINGLE socket used by the experiment runner."""
    if not discover_enabled:
        return connect_on(last_host, preferred_interface, timeout=3), last_host, preferred_interface
    # Confirm identity before ever issuing setpoints. Probe sockets are closed.
    devices = discover(last_host=last_host, preferred_interface=preferred_interface,
                       all_matches=True)
    if not devices:
        raise ConnectionError(
            'CPX400DP not found on active interfaces (attempted cached address, '
            'CSV address, ARP neighbours and mDNS). Check instrument power/cabling, '
            'or use Test connection to diagnose an unconfigured Ethernet adapter.')
    if len(devices) > 1:
        # Explicit preferred address wins, otherwise refuse ambiguous selection.
        chosen = [d for d in devices if d[0] == last_host and
                  (not preferred_interface or d[1] == preferred_interface)]
        if len(chosen) != 1:
            raise ConnectionError('Multiple CPX400DP instruments found: ' +
                                  '; '.join(f'{h} on {nic}' for h, nic, _ in devices) +
                                  '. Specify --psu-ip and --psu-interface.')
        devices = chosen
    host, nic, identity = devices[0]
    print(f'[PSU DISCOVERED] {host}:9221 via {nic} — {identity}', flush=True)
    try:
        s = connect_on(host, nic, timeout=3)
    except OSError as exc:
        raise ConnectionError(f'Discovered PSU at {host} on {nic}, but connection failed: {exc}') from exc
    cache_write(host, nic)
    return s, host, nic


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ip', default=None, help='Known PSU IP (optional)')
    p.add_argument('--interface', default=None, help='Linux network interface')
    a = p.parse_args()
    matches = discover(last_host=a.ip, preferred_interface=a.interface, all_matches=True)
    for host, nic, ident in matches:
        print(f'{host}:9221 interface={nic} identity={ident}')
    if not matches:
        print('No PSU identified. Supply --ip and/or --interface, or check the LAN connection.')
        raise SystemExit(1)
