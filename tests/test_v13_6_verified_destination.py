"""Offline regression for last-verified PSU destination persistence (no Qt or PSU)."""
import ast
import unittest
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / 'scripts' / 'cpx400dp_gui.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)
WINDOW = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'Window')

def body(name):
    method = next(n for n in WINDOW.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(SOURCE, method)

class VerifiedDestinationTests(unittest.TestCase):
    def test_restore_only_saved_values_without_network_on_launch(self):
        init = body('__init__')
        self.assertIn("self.settings.value('verified_psu_ip'", init)
        self.assertIn("self.settings.value('verified_psu_interface'", init)
        self.assertIn("ipaddress.IPv4Address(saved_ip)", init)
        self.assertIn("self.psu_ip.setText(saved_ip)", init)
        self.assertIn("self.psu_interface.findText(saved_iface) >= 0", init)
        self.assertIn("self.psu_interface.setCurrentText(saved_iface)", init)
        self.assertNotIn("diagnose_connection(", init)
        self.assertNotIn("self.settings.setValue('verified_psu_ip'", init)

    def test_persist_only_on_confirmed_probe(self):
        probe = body('connection_test_finished')
        self.assertIn("if result.get('status') == 'found':", probe)
        self.assertIn("self.settings.setValue('verified_psu_ip', host)", probe)
        self.assertIn("self.settings.setValue('verified_psu_interface', iface)", probe)
        self.assertIn("self.settings.sync()", probe)
        self.assertNotIn("self.settings.remove('verified_psu_ip')", probe)
        start = body('start_run')
        manual = body('connect_manual')
        self.assertNotIn("self.settings.setValue('verified_psu_ip'", start)
        self.assertNotIn("self.settings.setValue('verified_psu_ip'", manual)

    def test_existing_override_semantics_unchanged(self):
        init = body('__init__')
        self.assertIn("self.psu_ip.setPlaceholderText('CSV address / automatic discovery')", init)
        self.assertIn("self.psu_interface.addItem('Auto')", init)
        self.assertIn("self.psu_ip.text().strip()", body('start_run'))
        self.assertIn("self.psu_ip.text().strip()", body('connect_manual'))

if __name__ == '__main__':
    unittest.main()
