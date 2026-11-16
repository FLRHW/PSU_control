"""Offline network-dialog regression tests; no instrument or Qt runtime needed."""
import ast
import unittest
from pathlib import Path

SOURCE=(Path(__file__).resolve().parents[1]/'scripts'/'cpx400dp_gui.py').read_text()
TREE=ast.parse(SOURCE)
WINDOW=next(n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name=='Window')


def method(name):
    return next(n for n in WINDOW.body if isinstance(n,ast.FunctionDef) and n.name==name)


class NetworkDialogTests(unittest.TestCase):
    def test_qdialog_imported_in_both_qt_backends(self):
        # GitHub CI may have no Qt runtime; check both import branches.
        backends=('PySide6.QtWidgets','PyQt5.QtWidgets')
        for backend in backends:
            imports=[node for node in ast.walk(TREE)
                     if isinstance(node,ast.ImportFrom) and node.module==backend]
            self.assertEqual(len(imports),1,backend)
            symbols={alias.name for alias in imports[0].names}
            self.assertIn('QDialog',symbols,backend)

    def test_toolbar_has_only_network_settings_button(self):
        init=ast.get_source_segment(SOURCE,method('__init__'))
        toolbar=init.split("self.network_dialog = QDialog(self)",1)[0]
        self.assertIn("QPushButton('Network settings…')",toolbar)
        self.assertIn("selectors.addLayout(network_row)",toolbar)
        self.assertNotIn("connection_row.addWidget(self.psu_ip)",toolbar)
        self.assertNotIn("selectors.addWidget(self.connection_message)",init)

    def test_dialog_has_unclipped_fields_and_diagnostics(self):
        init=ast.get_source_segment(SOURCE,method('__init__'))
        for snippet in ("self.network_dialog.setMinimumWidth(680)",
                        "self.psu_ip.setMinimumWidth(230)",
                        "self.psu_interface.setMinimumWidth(230)",
                        "QPushButton('Test connection')",
                        "QPushButton('Prepare adapter…')",
                        "self.connection_message.setWordWrap(True)",
                        "close_network_btn.clicked.connect(self.network_dialog.hide)"):
            self.assertIn(snippet,init)
        self.assertNotIn("self.psu_ip.setMaximumWidth",init)
        self.assertEqual(init.count("self.test_connection_btn = QPushButton("),1)

    def test_opening_dialog_does_not_connect_or_configure(self):
        body=ast.get_source_segment(SOURCE,method('open_network_settings'))
        self.assertIn('self.network_dialog.show()',body)
        self.assertNotIn('diagnose_connection(',body)
        self.assertNotIn('setup_ethernet_link_local(',body)

    def test_runner_and_manual_use_same_values_and_safety_guards(self):
        for name in ('start_run','connect_manual','test_connection','prepare_adapter','run_finished','manual_done'):
            self.assertIsNotNone(method(name))
        self.assertIn('self.manual_worker is not None',ast.get_source_segment(SOURCE,method('test_connection')))
        self.assertIn('self.running',ast.get_source_segment(SOURCE,method('test_connection')))
        self.assertIn('QMessageBox.question(',ast.get_source_segment(SOURCE,method('prepare_adapter')))
        start=ast.get_source_segment(SOURCE,method('start_run'))
        self.assertIn('self.psu_ip.text().strip()',start)
        self.assertIn('self.psu_interface.currentText().strip()',start)


if __name__=='__main__':
    unittest.main()
