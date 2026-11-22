"""v12 discovery/report regression suite; no network connection or PSU commands."""
import contextlib
import csv
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import cpx400dp_discovery as discovery
import cpx400dp_report as report
import cpx400dp_run_enhanced as runner


class DiscoveryTests(unittest.TestCase):
    def test_interface_aware_wrong_default_route(self):
        """Explicit per-interface probe can find PSU despite bogus system default route."""
        with patch.object(discovery, 'interfaces', return_value={'enp3s0f1':['169.254.179.80'], 'enx0c3796303396':['169.254.10.1']}), \
             patch.object(discovery,'cache_read',return_value=None), \
             patch.object(discovery,'arp_candidates',return_value=[]), \
             patch.object(discovery,'probe',side_effect=lambda host, iface, timeout: 'THURLBY THANDAR,CPX400DP,1,2.0' if iface=='enx0c3796303396' else None), \
             patch.object(discovery,'cache_write') as save, \
             patch.object(discovery,'mdns_candidates',return_value=[]):
            found=discovery.discover(last_host='169.254.51.7',all_matches=True)
            self.assertEqual(found,[('169.254.51.7','enx0c3796303396','THURLBY THANDAR,CPX400DP,1,2.0')])

    def test_cache_and_manual_address_order(self):
        seen=[]
        with patch.object(discovery,'interfaces',return_value={'lan':['169.254.10.1']}), \
             patch.object(discovery,'cache_read',return_value=('169.254.5.5','lan')), \
             patch.object(discovery,'arp_candidates',return_value=[]), \
             patch.object(discovery,'probe',side_effect=lambda host, iface, timeout: seen.append(host) or None), \
             patch.object(discovery,'mdns_candidates',return_value=[]):
            discovery.discover(last_host='169.254.51.7')
        self.assertEqual(seen[:2],['169.254.51.7','169.254.5.5'])

    def test_dont_use_mdns_when_known_address_worked(self):
        with patch.object(discovery,'interfaces',return_value={'lan':['169.254.10.1']}), \
             patch.object(discovery,'cache_read',return_value=None), \
             patch.object(discovery,'arp_candidates',return_value=[]), \
             patch.object(discovery,'probe',return_value='CPX400DP'), \
             patch.object(discovery,'mdns_candidates',side_effect=AssertionError('Unnecessary multicast')), \
             patch.object(discovery,'cache_write'):
            result=discovery.discover(last_host='169.254.51.7')
        self.assertEqual(len(result),1)

    def test_mdns_fallback_for_moved_ip(self):
        with patch.object(discovery,'interfaces',return_value={'lan':['169.254.10.1']}), \
             patch.object(discovery,'cache_read',return_value=None), \
             patch.object(discovery,'arp_candidates',return_value=[]), \
             patch.object(discovery,'probe',side_effect=lambda host,iface,timeout: 'CPX400DP' if host=='169.254.34.10' else None), \
             patch.object(discovery,'mdns_candidates',return_value=['169.254.34.10']), \
             patch.object(discovery,'cache_write'):
            result=discovery.discover(last_host='169.254.51.7')
        self.assertEqual(result[0][:2],('169.254.34.10','lan'))

    def test_multiple_psus_refused_when_ambiguous(self):
        with patch.object(discovery,'discover',return_value=[('169.254.1.1','eth0','CPX400DP'),('169.254.2.2','eth0','CPX400DP')]):
            with self.assertRaisesRegex(ConnectionError,'Multiple CPX400DP'):
                discovery.connect_psu('169.254.99.99')

    def test_specific_host_selected_among_multiple(self):
        sock=MagicMock()
        with patch.object(discovery,'discover',return_value=[('169.254.1.1','eth0','CPX400DP'),('169.254.2.2','eth1','CPX400DP')]), \
             patch.object(discovery,'connect_on',return_value=sock) as connect, \
             patch.object(discovery,'cache_write'):
            s,host,nic=discovery.connect_psu('169.254.2.2')
        self.assertIs(s,sock)
        self.assertEqual((host,nic),('169.254.2.2','eth1'))
        connect.assert_called_once_with('169.254.2.2','eth1',timeout=3)

    def test_unknown_device_not_accepted(self):
        class FakeSocket:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def sendall(self,raw):self.query=raw
            def recv(self,n):return b'OTHER,VNA,1,0\n'
            def close(self):self.closed=True
        with patch.object(discovery,'connect_on',return_value=FakeSocket()):
            self.assertIsNone(discovery.probe('169.254.51.7','lan'))

    def test_no_match_gives_actionable_exception(self):
        with patch.object(discovery,'discover',return_value=[]):
            with self.assertRaisesRegex(ConnectionError,'not found on active interfaces'):
                discovery.connect_psu('169.254.51.7')

    def test_no_connection_during_invalid_profile(self):
        profile=Path(__file__).resolve().parents[1] / 'profiles' / 'negative_tests' / '14_REJECT_40ms_INTERVAL_OFFLINE_ONLY.csv'
        with patch.object(discovery,'connect_psu',side_effect=AssertionError('must not connect')):
            with self.assertRaisesRegex(ValueError,'50|short|interval|gap|safe|scheduled'):
                runner.execute(profile)

    def test_host_interface_binder(self):
        fake=MagicMock()
        with patch.object(discovery.socket,'socket',return_value=fake) as constructor, \
             patch.object(discovery,'interfaces',return_value={'enx0c3796303396':['169.254.51.8']}):
            result=discovery.connect_on('169.254.51.7','enx0c3796303396')
        self.assertIs(result,fake)
        self.assertEqual(fake.connect.call_args.args[0],('169.254.51.7',9221))
        self.assertIn(b'enx0c3796303396',fake.setsockopt.call_args_list[0].args[2])
        fake.bind.assert_called_once_with(('169.254.51.8',0))

class ReportTests(unittest.TestCase):
    def test_report_has_offline_zoom_and_cursors(self):
        sample=Path('/mnt/data/15_measurements_20261115_085658_842524.csv')
        if not sample.exists():self.skipTest('Uploaded HW data not mounted')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sample.csv';p.write_bytes(sample.read_bytes())
            html=report.generate(p).read_text()
            for phrase in ('Reset zoom','Cursors: OFF','wheel','pointerdown','pointermove','cursor-values','Δt','ΔV','clipPath'):
                self.assertIn(phrase,html)
            self.assertIn('CPX400DP — experiment report',html)

    def test_generated_page_is_standalone(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sample.csv'
            with p.open('w',newline='') as f:
                wr=csv.DictWriter(f,fieldnames=runner.LOG_FIELDS)
                wr.writeheader()
                wr.writerows([
                    {'event':'readback','channel':'1','elapsed_s':'0.1','measured_voltage_v':'1.2','measured_current_a':'.1'},
                    {'event':'readback','channel':'1','elapsed_s':'0.2','measured_voltage_v':'2.2','measured_current_a':'.2'},
                    {'event':'final_state_verified','channel':'1'}])
            content=report.generate(p).read_text()
            self.assertNotIn('src="http',content)
            self.assertNotIn('<script src=',content)

if __name__=='__main__':unittest.main()
