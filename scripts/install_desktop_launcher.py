#!/usr/bin/env python3
"""Install/remove a KDE/Linux app-menu launcher for this repository checkout.

User-local XDG locations only. No root privileges, extra packages or PSU I/O.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile

APP_ID = "cpx400dp-control"
MANAGED_MARKER = "X-CPX400DP-Managed=true"
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cpx400dp_gui.py"
ICON = ROOT / "assets" / (APP_ID + ".svg")


def desktop_arg(arg: str) -> str:
    """Quote a path for Desktop Entry Exec, including reserved characters."""
    value = str(arg)
    for source, replacement in (
        ("\\", "\\\\"), ('"', '\\"'), ("$", "\\$"), (chr(96), "\\" + chr(96))
    ):
        value = value.replace(source, replacement)
    return '"' + value + '"'


def xdg_paths():
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    return (base / "applications" / (APP_ID + ".desktop"),
            base / "icons/hicolor/scalable/apps" / (APP_ID + ".svg"))


def launcher_content(python_executable: Path, installed_icon: Path) -> str:
    return "\n".join([
        "[Desktop Entry]",
        "Version=1.0",
        "Type=Application",
        "Name=CPX400DP Control",
        "GenericName=Programmable Power Supply Controller",
        "Comment=Control and record TTi CPX400DP PSU experiments",
        "Exec=" + desktop_arg(str(python_executable)) + " " + desktop_arg(str(SCRIPT)),
        "TryExec=" + str(python_executable),
        "Path=" + str(ROOT),
        "Icon=" + str(installed_icon),
        "Terminal=false",
        "Categories=Development;Science;",
        "StartupNotify=true",
        "StartupWMClass=" + APP_ID,
        MANAGED_MARKER,
        ""
    ])


def managed(path: Path) -> bool:
    try:
        return (path.is_file() and MANAGED_MARKER in
                path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeError):
        return False


def write_atomic(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".cpx400dp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def install(python_executable: Path, dry_run: bool = False):
    if not SCRIPT.is_file() or not ICON.is_file():
        raise RuntimeError("Cannot find GUI script/icon beside the installer")
    if not python_executable.is_file() or not os.access(python_executable, os.X_OK):
        raise RuntimeError("Python executable not found: " + str(python_executable))
    entry, icon_path = xdg_paths()
    if entry.exists() and not managed(entry):
        raise RuntimeError("Refusing to overwrite an unrelated desktop entry: " + str(entry))
    if icon_path.exists() and not managed(entry) and icon_path.read_bytes() != ICON.read_bytes():
        raise RuntimeError("Refusing to overwrite an unrelated icon: " + str(icon_path))
    data = launcher_content(python_executable, icon_path).encode("utf-8")
    print("Launcher:", entry)
    print("Icon:", icon_path)
    print("Runs:", python_executable, SCRIPT)
    if dry_run:
        print("Dry run: nothing changed")
        return
    write_atomic(icon_path, ICON.read_bytes())
    write_atomic(entry, data)
    entry.chmod(0o644)
    print("Installed. Search for 'CPX400DP Control' in the KDE Application Launcher.")
    print("Right-click it to add to Favorites or pin to Task Manager.")


def uninstall(dry_run: bool = False):
    entry, icon_path = xdg_paths()
    if not entry.exists():
        print("Launcher not installed:", entry)
        return
    if not managed(entry):
        raise RuntimeError("Refusing to remove an unrelated desktop entry: " + str(entry))
    if dry_run:
        print("Would remove launcher:", entry)
        print("Would remove matching original icon (if unchanged):", icon_path)
        return
    entry.unlink()
    if icon_path.is_file() and ICON.exists() and icon_path.read_bytes() == ICON.read_bytes():
        icon_path.unlink()
    print("Removed CPX400DP launcher; project files unchanged.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uninstall", action="store_true",
                        help="Remove only the launcher installed by this script")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show actions without writing or deleting anything")
    parser.add_argument("--python", type=Path, default=Path(sys.executable),
                        help="Python interpreter for launcher (default: this Python)")
    opts = parser.parse_args(argv)
    try:
        if opts.uninstall:
            uninstall(dry_run=opts.dry_run)
        else:
            install(opts.python.resolve(), dry_run=opts.dry_run)
    except (OSError, RuntimeError) as error:
        parser.exit(1, "Launcher error: " + str(error) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
