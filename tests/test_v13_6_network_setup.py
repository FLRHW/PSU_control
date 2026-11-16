"""v13.6 Ethernet discovery/setup regression tests; NO hardware I/O."""
import json
import types
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

import cpx400dp_network_setup as net
import cpx400dp_discovery as discovery


DOCK={'name':'enx0c3796303396','ipv4':[],'carrier':True,
      'kind':'ethernet','mac':'0c:37:96:30:33:96'}
RIGOL={'name':'enp3s0f1','ipv4':['169.254.10.1'],'carrier':True,
       'kind':'ethernet'}
WIFI={'name':'wlp4s0','ipv4':[],'carrier':True,'kind':'wifi'}


class NetworkSetupTests(unittest.TestCase):
    def test_dock_with_no_ipv4_is_visible(self):
        addresses=[
            {'ifname':'enx0c3796303396','link_type':'ether','operstate':'UP',
             'flags':['BROADCAST','UP','LOWER_UP'],'address':'0c:37:96:30:33:96','addr_info':[]},
            {'ifname':'enp3s0f1','link_type':'ether','operstate':'UP',
             'flags':['BROADCAST','UP','LOWER_UP'],'addr_info':[{'family':'inet','local':'169.254.10.1'}]},
        ]
        with patch.object(net.subprocess,'run',return_value=types.SimpleNamespace(stdout=json.dumps(addresses))), \
             patch.object(Path,'exists',autospec=True,side_effect=lambda path: path.name=='device'):
            result=net.adapter_details()
        self.assertEqual(result[0]['ipv4'],[])
        self.assertEqual(result[0]['kind'],'ethernet')
        self.assertTrue(net.is_setup_candidate(result[0]))
        self.assertEqual(result[1]['ipv4'],['169.254.10.1'])

    def test_setup_never_touches_wifi_or_existing_ipv4(self):
        for item in (WIFI,RIGOL,{**DOCK,'carrier':False},{**DOCK,'kind':'virtual'}):
            self.assertFalse(net.is_setup_candidate(item))
            with patch.object(net,'adapter_details',return_value=[item]):
                runner=Mock()
                with self.assertRaises(ValueError):
                    net.setup_ethernet_link_local(item['name'],runner=runner)
                runner.assert_not_called()

    def test_opt_in_setup_only_issues_scoped_nmcli_commands(self):
        calls=[]
        def run(args,**kw):
            calls.append(args)
            if args[0] == 'ip':
                return types.SimpleNamespace(stdout='[]')
            return types.SimpleNamespace(stdout='--')
        with patch.object(net,'adapter_details',return_value=[DOCK]):
            result=net.setup_ethernet_link_local(DOCK['name'],runner=run)
        self.assertEqual(result,'CPX400DP-direct-enx0c3796303396')
        self.assertEqual(len(calls),4)
        self.assertEqual(calls[0][:4],['nmcli','-g','GENERAL.CONNECTION','device'])
        self.assertEqual(calls[1][:3],['ip','-j','-4'])
        self.assertIn('link-local',calls[2])
        self.assertEqual(calls[3][:3],['nmcli','connection','up'])
        self.assertTrue(all(isinstance(arg,list) for arg in calls))

    def test_setup_rejects_route_conflict_without_creating_profile(self):
        calls=[]
        def run(args,**kw):
            calls.append(args)
            if args[0] == 'ip':
                return types.SimpleNamespace(stdout=json.dumps([
                    {'dst':'169.254.0.0/16','dev':'enp3s0f1'},
                    {'dst':'169.254.179.79','dev':'enp3s0f1'}]))
            return types.SimpleNamespace(stdout='--')
        with patch.object(net,'adapter_details',return_value=[DOCK]):
            with self.assertRaisesRegex(ValueError,'Existing link-local'):
                net.setup_ethernet_link_local(DOCK['name'],runner=run)
        self.assertEqual(len(calls),2)
        self.assertFalse(any('add' in args for args in calls))

    def test_route_summary_no_overlap_warns_about_disconnected_interfaces(self):
        runner=Mock(return_value=types.SimpleNamespace(stdout='[]'))
        message=net.network_route_summary(runner=runner)
        self.assertIn('currently',message)
        self.assertIn('connected',message)

    def test_existing_nm_connection_refused(self):
        with patch.object(net,'adapter_details',return_value=[DOCK]):
            runner=Mock(return_value=types.SimpleNamespace(stdout='Wired connection 1\\n'))
            with self.assertRaisesRegex(ValueError,'active NetworkManager'):
                net.setup_ethernet_link_local(DOCK['name'],runner=runner)
            runner.assert_called_once()

    def test_read_only_diagnosis_lists_setup_candidate(self):
        with patch.object(net,'adapter_details',return_value=[DOCK,RIGOL]), \
             patch.object(discovery,'discover',return_value=[]):
            outcome=net.diagnose_connection('169.254.51.7')
        self.assertEqual(outcome['status'],'unconfigured')
        self.assertEqual(outcome['setup'],[DOCK['name']])

    def test_read_only_diagnosis_selects_unique_identity(self):
        with patch.object(net,'adapter_details',return_value=[DOCK,RIGOL]), \
             patch.object(discovery,'discover',return_value=[('169.254.51.7',DOCK['name'],'TTi,CPX400DP,1234,1')]):
            outcome=net.diagnose_connection('169.254.51.7')
        self.assertEqual(outcome['status'],'found')
        self.assertEqual(outcome['matches'][0][1],DOCK['name'])

    def test_multiple_matching_devices_does_not_pick_arbitrarily(self):
        found=[('169.254.51.7','enx0c3796303396','CPX400DP'),
               ('169.254.24.8','enp3s0f1','CPX400DP')]
        with patch.object(net,'adapter_details',return_value=[DOCK,RIGOL]), \
             patch.object(discovery,'discover',return_value=found):
            result=net.diagnose_connection()
        self.assertEqual(result['status'],'multiple')

    def test_route_audit_finds_overlapping_interface_networks(self):
        routes=[{'dst':'169.254.0.0/16','dev':'enp3s0f1'},
                {'dst':'169.254.0.0/16','dev':'enx0c3796303396'},
                {'dst':'169.254.179.79','dev':'enp3s0f1'},
                {'dst':'192.168.0.0/24','dev':'wlp4s0'}]
        runner=Mock(return_value=types.SimpleNamespace(stdout=json.dumps(routes)))
        overlaps=net.overlapping_ipv4_routes(runner=runner)
        self.assertEqual(len(overlaps),1)
        self.assertIn('169.254.0.0/16',str(overlaps[0]))
        message=net.network_route_summary(runner=runner)
        self.assertIn('Overlapping',message)
        self.assertIn('enp3s0f1',message)
        runner.assert_called()
        self.assertEqual(runner.call_args.args[0][:3],['ip','-j','-4'])

    def test_distinct_networks_and_host_routes_are_not_a_conflict(self):
        routes=[{'dst':'192.168.50.0/24','dev':'dock'},
                {'dst':'169.254.0.0/16','dev':'rigol'},
                {'dst':'169.254.51.7','dev':'dock'}]
        runner=Mock(return_value=types.SimpleNamespace(stdout=json.dumps(routes)))
        self.assertEqual(net.overlapping_ipv4_routes(runner=runner),[])
        self.assertIn('No overlapping',net.network_route_summary(runner=runner))

    def test_gui_profile_connection_and_csv_directory_controls(self):
        source=(Path(__file__).resolve().parents[1]/'scripts'/'cpx400dp_gui.py').read_text()
        self.assertIn("QPushButton('Test connection')",source)
        self.assertIn("QPushButton('Prepare adapter…')",source)
        self.assertIn("self.settings.setValue('last_profile_directory'",source)
        self.assertIn("first_use = HERE.parent / 'profiles'",source)
        self.assertIn('self.manual_worker is not None',source)
        self.assertIn('AdapterSetupJob',source)


if __name__=='__main__':
    unittest.main()
