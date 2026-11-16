"""One-session *IDN? discovery and cleanup regression tests; hardware-free."""
import ast
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cpx400dp_discovery as discovery
import cpx400dp_run_enhanced as runner


class FakeSocket:
    def __init__(self, response=b'THURLBY THANDAR,CPX400DP,446696,2.00-4.06\n'):
        self.response=response
        self.sent=[]
        self.closed=False
    def sendall(self, data):
        self.sent.append(data)
    def recv(self, count):
        result,self.response=self.response[:count],self.response[count:]
        return result
    def close(self):
        self.closed=True


class ConnectionOwnershipTests(unittest.TestCase):
    def fixture(self, records):
        """Return patched context for discovery, no real network traffic."""
        return (
            patch.object(discovery,'interfaces',return_value={'eth_dock':['169.254.51.8'],
                                                               'eth_rigol':['169.254.10.1']}),
            patch.object(discovery,'cache_read',return_value=None),
            patch.object(discovery,'arp_candidates',return_value=[]),
            patch.object(discovery,'mdns_candidates',return_value=[]),
            patch.object(discovery,'cache_write'),
            patch.object(discovery,'connect_on',side_effect=lambda host,interface,timeout=.65: records[(host,interface)])
        )

    def test_control_socket_is_the_one_that_answered_idn(self):
        dock=FakeSocket()
        wrong=FakeSocket(b'RIGOL TECHNOLOGIES,DS1054Z,123,1.0\n')
        sockets={('169.254.51.7','eth_dock'):dock,
                 ('169.254.51.7','eth_rigol'):wrong}
        patches=self.fixture(sockets)
        for cm in patches: cm.__enter__()
        try:
            sock,host,iface=discovery.connect_psu('169.254.51.7')
        finally:
            for cm in reversed(patches): cm.__exit__(None,None,None)
        self.assertIs(sock,dock)
        self.assertEqual((host,iface),('169.254.51.7','eth_dock'))
        self.assertEqual(dock.sent,[b'*IDN?\n'])
        self.assertFalse(dock.closed,'verified control socket must remain open')
        self.assertTrue(wrong.closed,'unrelated instrument must be disconnected')
        sock.close()

    def test_ambiguous_devices_are_all_closed_without_commands(self):
        a=FakeSocket(); b=FakeSocket()
        sockets={('169.254.51.7','eth_dock'):a,
                 ('169.254.51.7','eth_rigol'):b}
        patches=self.fixture(sockets)
        for cm in patches: cm.__enter__()
        try:
            with self.assertRaisesRegex(ConnectionError,'Multiple CPX400DP'):
                discovery.connect_psu('169.254.51.7',preferred_interface=None)
        finally:
            for cm in reversed(patches): cm.__exit__(None,None,None)
        self.assertTrue(a.closed)
        self.assertTrue(b.closed)
        self.assertEqual(a.sent,[b'*IDN?\n'])
        self.assertEqual(b.sent,[b'*IDN?\n'])

    def test_normal_gui_discovery_closes_test_socket(self):
        sock=FakeSocket()
        with patch.object(discovery,'connect_on',return_value=sock):
            ident=discovery.probe('169.254.51.7','eth_dock')
        self.assertIn('CPX400DP',ident)
        self.assertTrue(sock.closed)

    def test_failed_identity_closes_socket(self):
        sock=FakeSocket(b'OTHER,DEVICE,1,2\n')
        with patch.object(discovery,'connect_on',return_value=sock):
            self.assertIsNone(discovery.identify_connection('169.254.51.7','eth_dock'))
        self.assertTrue(sock.closed)

    def test_runner_only_emits_preflight_message_before_snapshot(self):
        source=(Path(__file__).resolve().parents[1]/'scripts'/'cpx400dp_run_enhanced.py').read_text()
        block=source.index("sock, resolved_host, resolved_interface = connect_psu(")
        initial=source.index("verify_initial_snapshot(sock, channels, pending)",block)
        self.assertIn('[CONNECTION NOT ESTABLISHED]',source[block:initial])
        gui=(Path(__file__).resolve().parents[1]/'scripts'/'cpx400dp_gui.py').read_text()
        self.assertIn('self.connection_not_established = True',gui)
        self.assertIn("'PSU connection failed'",gui)


if __name__ == '__main__':
    unittest.main()
