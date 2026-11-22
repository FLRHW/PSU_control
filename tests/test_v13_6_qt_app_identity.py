"""Offscreen Qt verification of KDE desktop-file identity and window icon.

No PSU/network operations and no Plasma desktop required.
"""
import unittest
from pathlib import Path


class DesktopIdentityTests(unittest.TestCase):
    def test_qt_application_identifies_as_desktop_launcher(self):
        from cpx400dp_gui import (
            QApplication, QIcon, DESKTOP_APP_ID, APPLICATION_ICON,
            configure_desktop_identity,
        )
        self.assertEqual(DESKTOP_APP_ID, 'cpx400dp-control')
        self.assertTrue(Path(APPLICATION_ICON).is_file())
        app = QApplication.instance() or QApplication([])
        configure_desktop_identity(app)
        self.assertEqual(app.applicationName(), DESKTOP_APP_ID)
        self.assertEqual(app.applicationDisplayName(), 'CPX400DP Control')
        self.assertEqual(app.desktopFileName(), DESKTOP_APP_ID)
        self.assertFalse(app.windowIcon().isNull())
        self.assertFalse(app.windowIcon().pixmap(64, 64).isNull())
        self.assertFalse(QIcon(str(APPLICATION_ICON)).isNull())

    def test_main_window_sets_own_icon(self):
        import ast
        from cpx400dp_gui import APPLICATION_ICON
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'cpx400dp_gui.py'
        source = path.read_text()
        tree = ast.parse(source)
        window = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                      and node.name == 'Window')
        init = next(node for node in window.body if isinstance(node, ast.FunctionDef)
                    and node.name == '__init__')
        fragment = ast.get_source_segment(source, init)
        self.assertIn('self.setWindowIcon(QIcon(str(APPLICATION_ICON)))', fragment)
        self.assertTrue(APPLICATION_ICON.exists())


if __name__ == '__main__':
    unittest.main()
