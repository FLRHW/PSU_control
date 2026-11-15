"""Regression guards for output state UI and direct resume controls."""
import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

SOURCE = (Path(__file__).resolve().parents[1] / 'scripts' / 'cpx400dp_gui.py').read_text()


def window_method(name):
    tree = ast.parse(SOURCE)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Window')
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)


class ManualUiTests(unittest.TestCase):
    def test_buttons_depend_on_confirmed_output_state(self):
        method = window_method('manual_widgets_enabled')
        ns = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'manual_widgets_enabled', 'exec'), ns)
        on, off = Mock(), Mock()
        obj = SimpleNamespace(manual_cards={1: (None, None, on, off), 2: (None, None, Mock(), Mock()),
                                               (1, 'voltage'): (None, Mock()), (1, 'current'): (None, Mock()),
                                               (2, 'voltage'): (None, Mock()), (2, 'current'): (None, Mock())},
                              manual_output_states={1:True, 2:False},pause_manual_active=False,
                              manual_disconnect_btn=Mock(),manual_resume_btn=Mock(),
                              running=False,paused=False,stopping=False)
        ns['manual_widgets_enabled'](obj, True)
        on.setEnabled.assert_called_with(False)
        off.setEnabled.assert_called_with(True)
        obj.manual_cards[2][2].setEnabled.assert_called_with(True)
        obj.manual_cards[2][3].setEnabled.assert_called_with(False)

    def test_resume_without_confirmation(self):
        fn=window_method('toggle_pause')
        text=ast.get_source_segment(SOURCE, fn)
        self.assertNotIn('QMessageBox.question', text)
        self.assertIn('os.kill(pid, signal.SIGUSR1)', text)
        self.assertIn('manual_widgets_enabled(False)', text)

    def test_prominent_colour_output_indicators(self):
        self.assertIn("indicator.setText('● OUTPUT ON')",SOURCE)
        self.assertIn("indicator.setText('○ OUTPUT OFF')",SOURCE)
        self.assertIn('self.manual_output_states[ch] = bool(enabled)',SOURCE)

if __name__ == '__main__': unittest.main()
