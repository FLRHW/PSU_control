"""Tests GUI display decisions without requiring Qt or a PSU."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


def gui_fn(name):
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'scripts' / 'cpx400dp_gui.py').read_text())
    window = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'Window')
    node = next(x for x in window.body if isinstance(x, ast.FunctionDef) and x.name == name)
    ns = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<GUI method>', 'exec'), ns)
    return ns[name]


class DisplayTests(unittest.TestCase):
    def make_gui(self, enabled, checked, csv_channels=(1, 2)):
        return SimpleNamespace(
            _setting_defaults={'channels': list(csv_channels)},
            override_check=SimpleNamespace(isChecked=lambda: enabled),
            channel_indicators={i: SimpleNamespace(isChecked=lambda i=i: i in checked) for i in (1, 2)},
            channel_labels={i: Mock() for i in (1, 2)},
            restore_labels={i: Mock() for i in (1, 2)},
        )

    def test_idle_single_channel_marks_other_na(self):
        gui = self.make_gui(True, (1,))
        gui.displayed_channels = lambda: gui_fn('displayed_channels')(gui)
        gui_fn('set_channel_status_idle')(gui)
        gui.restore_labels[1].setText.assert_called_with('Restoration: not checked')
        gui.restore_labels[2].setText.assert_called_with('N/A — channel not selected')

    def test_csv_channels_when_override_disabled(self):
        gui = self.make_gui(False, (2,))
        self.assertEqual(gui_fn('displayed_channels')(gui), {1, 2})

    def test_absent_csv_channel_never_selected(self):
        gui = self.make_gui(True, (1, 2), csv_channels=(1,))
        self.assertEqual(gui_fn('displayed_channels')(gui), {1})

    def test_single_preview_has_spacers_on_both_sides(self):
        source = (Path(__file__).resolve().parents[1] / 'scripts' / 'cpx400dp_gui.py').read_text()
        tree = ast.parse(source)
        win = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Window')
        method = next(n for n in win.body if isinstance(n, ast.FunctionDef) and n.name == 'display_preview_pixmaps')
        calls = [n for n in ast.walk(method) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'addStretch']
        self.assertEqual(len(calls), 2)


if __name__ == '__main__':
    unittest.main()
