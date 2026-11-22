"""Offline tests: KDE launcher installer never touches PSU or real XDG settings."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts" / "install_desktop_launcher.py"
SPEC = importlib.util.spec_from_file_location("cpx_desktop_installer", FILE)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class DesktopLauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / "repository with spaces"
        (self.root / "scripts").mkdir(parents=True)
        (self.root / "assets").mkdir()
        self.script = self.root / "scripts" / "cpx400dp_gui.py"
        self.icon = self.root / "assets" / "cpx400dp-control.svg"
        self.script.write_text("print('GUI placeholder')\n")
        self.icon.write_text("<svg/>")
        self.home_data = base / "XDG data"
        self.env = patch.dict(os.environ, {"XDG_DATA_HOME": str(self.home_data)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.patch_root = patch.object(installer, "ROOT", self.root)
        self.patch_script = patch.object(installer, "SCRIPT", self.script)
        self.patch_icon = patch.object(installer, "ICON", self.icon)
        for handle in (self.patch_root, self.patch_script, self.patch_icon):
            handle.start()
            self.addCleanup(handle.stop)

    def test_install_reinstall_and_uninstall_are_safe(self):
        installer.install(Path(sys.executable))
        entry, installed_icon = installer.xdg_paths()
        self.assertTrue(entry.exists())
        self.assertEqual(installed_icon.read_bytes(), self.icon.read_bytes())
        text = entry.read_text()
        self.assertIn('Name=CPX400DP Control', text)
        self.assertIn('Exec="' + str(Path(sys.executable)) + '" "' +
                      str(self.script) + '"', text)
        self.assertIn('Path=' + str(self.root), text)
        self.assertIn('Icon=' + str(installed_icon), text)
        self.assertIn('Terminal=false', text)
        self.assertIn(installer.MANAGED_MARKER, text)
        installer.install(Path(sys.executable))
        installer.uninstall()
        self.assertFalse(entry.exists())
        self.assertFalse(installed_icon.exists())
        self.assertTrue(self.script.exists())

    def test_dry_run_never_writes_files(self):
        installer.install(Path(sys.executable), dry_run=True)
        entry, icon = installer.xdg_paths()
        self.assertFalse(entry.exists())
        self.assertFalse(icon.exists())

    def test_unrelated_desktop_entry_is_protected(self):
        entry, _ = installer.xdg_paths()
        entry.parent.mkdir(parents=True)
        entry.write_text("[Desktop Entry]\nName=Other program\n")
        with self.assertRaisesRegex(RuntimeError, "unrelated"):
            installer.install(Path(sys.executable))
        with self.assertRaisesRegex(RuntimeError, "unrelated"):
            installer.uninstall()
        self.assertIn('Other program', entry.read_text())

    def test_modified_icon_is_not_deleted(self):
        installer.install(Path(sys.executable))
        entry, icon = installer.xdg_paths()
        icon.write_text("user customised icon")
        installer.uninstall()
        self.assertFalse(entry.exists())
        self.assertEqual(icon.read_text(), "user customised icon")

    def test_exec_escapes_special_characters(self):
        escaped = installer.desktop_arg('/tmp/path with "quotes", $cash and \\slashed')
        self.assertEqual(escaped, '"/tmp/path with \\"quotes\\", \\$cash and \\\\slashed"')

    def test_uninstall_dry_run_does_not_delete(self):
        installer.install(Path(sys.executable))
        entry, icon = installer.xdg_paths()
        installer.uninstall(dry_run=True)
        self.assertTrue(entry.exists())
        self.assertTrue(icon.exists())


if __name__ == "__main__":
    unittest.main()
