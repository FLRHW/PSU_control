"""Offline tests for read-only persistence assessment (no real ip/nmcli calls)."""
import json
import types
import unittest
from unittest.mock import Mock

import cpx400dp_network_preflight as preflight


def response(output):
    return types.SimpleNamespace(stdout=output)


class PreflightTests(unittest.TestCase):
    def test_overlapping_dock_external_and_unsaved_rigol_host_route(self):
        commands = []
        routes = [
            {'dst': '169.254.0.0/16', 'dev': 'enx0c3796303396'},
            {'dst': '169.254.0.0/16', 'dev': 'enp3s0f1', 'metric': 100},
            {'dst': '169.254.179.79', 'dev': 'enp3s0f1'},
            {'dst': '192.168.0.0/24', 'dev': 'wlp4s0'},
        ]
        addrs = [
            {'ifname': 'enp3s0f1',
             'addr_info': [{'family': 'inet', 'local': '169.254.10.1', 'prefixlen': 16}]},
            {'ifname': 'enx0c3796303396',
             'addr_info': [{'family': 'inet', 'local': '169.254.51.8', 'prefixlen': 16}]},
        ]
        def run(args, **kwargs):
            commands.append(args)
            if args[:4] == ['ip', '-j', '-4', 'route']:
                if 'get' in args:
                    return response(json.dumps([{'dev': 'enx0c3796303396',
                                                'prefsrc': '169.254.51.8'}]))
                return response(json.dumps(routes))
            if args[:4] == ['ip', '-j', '-4', 'addr']:
                return response(json.dumps(addrs))
            if args[:4] == ['nmcli', '-g', 'GENERAL.STATE', 'device']:
                return response('100 (connected (externally))' if args[-1].startswith('enx')
                                else '100 (connected)')
            if args[:4] == ['nmcli', '-g', 'GENERAL.CONNECTION', 'device']:
                return response(args[-1] if args[-1].startswith('enx')
                                else 'Wired connection 2')
            if args[:3] == ['nmcli', '-g', 'ipv4.method']:
                return response('manual')
            if args[:3] == ['nmcli', '-g', 'ipv4.addresses']:
                return response('169.254.10.1/16')
            if args[:3] == ['nmcli', '-g', 'ipv4.routes']:
                return response('')
            if args[:3] == ['nmcli', '-g', 'connection.autoconnect']:
                return response('yes')
            raise AssertionError(args)
        report = preflight.persistence_preflight('169.254.51.7', runner=run)
        self.assertIn('Multiple interfaces', report)
        self.assertIn('connected externally', report)
        self.assertIn('WARNING: active host route 169.254.179.79/32', report)
        self.assertIn('169.254.51.7 via enx0c3796303396', report)
        self.assertIn('No routes, profiles, addresses or instrument settings', report)
        self.assertTrue(all(args[0] in ('ip', 'nmcli') for args in commands))
        self.assertFalse(any(word in args for args in commands for word in
                             ('add', 'replace', 'delete', 'modify', 'up', 'down')))

    def test_disconnected_rigol_is_reported_even_without_route(self):
        routes = [{'dst': '169.254.0.0/16', 'dev': 'enx0c3796303396'}]
        addresses = [
            {'ifname': 'enx0c3796303396', 'link_type': 'ether',
             'addr_info': [{'family': 'inet', 'local': '169.254.51.8',
                            'prefixlen': 16}]},
            {'ifname': 'enp3s0f1', 'link_type': 'ether',
             'addr_info': [{'family': 'inet', 'local': '169.254.10.1',
                            'prefixlen': 16}]},
            {'ifname': 'wlp4s0', 'link_type': 'ether',
             'addr_info': [{'family': 'inet', 'local': '192.168.0.252',
                            'prefixlen': 24}]},
        ]
        def runner(args, **kw):
            if args[0] == 'ip':
                return response(json.dumps(addresses if 'addr' in args else routes))
            if args[:3] == ['nmcli', '-g', 'GENERAL.STATE']:
                return response('30 (disconnected)' if args[-1] == 'enp3s0f1'
                                else '100 (connected (externally))')
            if args[:3] == ['nmcli', '-g', 'GENERAL.CONNECTION']:
                return response('--' if args[-1] == 'enp3s0f1' else args[-1])
            raise AssertionError(args)
        report = preflight.persistence_preflight(runner=runner)
        self.assertIn('One currently observed link-local interface', report)
        self.assertIn('interfaces present without an active link-local route: enp3s0f1', report)
        self.assertIn('Adapter enp3s0f1:', report)
        self.assertIn('No current link-local route on this interface', report)
        self.assertIn('30 (disconnected)', report)
        self.assertNotIn('Adapter wlp4s0:', report)

    def test_saved_nm_host_route_is_not_flagged_unsaved(self):
        routes = [{'dst':'169.254.0.0/16','dev':'eth0'},
                  {'dst':'169.254.179.79','dev':'eth0'}]
        def run(args, **kw):
            if args[0] == 'ip':
                return response(json.dumps(routes if 'route' in args else
                    [{'ifname':'eth0','addr_info':[{'family':'inet',
                        'local':'169.254.10.1','prefixlen':16}]}]))
            field = args[2]
            if field == 'GENERAL.STATE':
                return response('100 (connected)')
            if field == 'GENERAL.CONNECTION':
                return response('Lab Rigol')
            return response('manual')
        # ensure actual saved-route field is evaluated rather than false assumed
        def run_with_routes(args, **kw):
            if args[:3] == ['nmcli', '-g', 'ipv4.routes']:
                return response('169.254.179.79/32')
            return run(args, **kw)
        report = preflight.persistence_preflight(runner=run_with_routes)
        self.assertIn('appears in saved NetworkManager', report)
        self.assertNotIn('WARNING: active host route', report)

    def test_invalid_psu_host_never_injects_commands(self):
        commands=[]
        def run(args, **kw):
            commands.append(args)
            if args[0] == 'ip' and 'addr' in args:
                return response('[]')
            return response('[]')
        report = preflight.persistence_preflight('hostname; rm -rf /',
                                                 runner=run)
        self.assertIn('invalid IPv4', report)
        self.assertFalse(any('route' in cmd and 'get' in cmd for cmd in commands))

    def test_gui_contains_async_worker_and_read_only_dialog(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1]/
                'scripts'/'cpx400dp_gui.py').read_text()
        for token in ('class PersistencePreflightJob(QThread)',
                      "QPushButton('Assess persistence')",
                      'self.persistence_preflight_job.start()',
                      'view.setReadOnly(True)',
                      'def persistence_preflight_finished'):
            self.assertIn(token, source)


if __name__ == '__main__':
    unittest.main()
