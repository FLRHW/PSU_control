#!/usr/bin/env python3
"""Manual control transport for CPX400DP. No profile-runner communication sharing.

Only one socket is held, by one dedicated Qt thread. All SCPI operations are
serialised. Disconnect preserves user's programmed values and sends LOCAL last.
"""
import queue
import time
try:
    from PySide6.QtCore import QThread, Signal as pyqtSignal
except ImportError:
    from PyQt5.QtCore import QThread, pyqtSignal
from cpx400dp_discovery import connect_psu
from cpx400dp_run_enhanced import send, measure, snapshot, verify_initial_snapshot


class ManualWorker(QThread):
    connected = pyqtSignal(str)
    state_changed = pyqtSignal(object, object)
    failed = pyqtSignal(str)
    finished_safe = pyqtSignal(str)

    def __init__(self, ip, interface=None, parent=None):
        super().__init__(parent)
        self.ip = ip
        self.interface = interface
        self.commands = queue.Queue()
        self.shutting_down = False

    def request(self, command, channel=None, value=None):
        if command == 'disconnect':
            self.shutting_down = True
        self.commands.put((command, channel, value))

    def run(self):
        sock = None
        pending = b''
        reason = 'Disconnected; LOCAL sent last'
        try:
            sock, host, iface = connect_psu(self.ip, self.interface)
            sock.settimeout(2.0)
            initial, pending = verify_initial_snapshot(sock, [1, 2], pending)
            self.connected.emit(f'{host}:9221 via {iface or "system route"}')
            self.state_changed.emit(initial, {})
            next_poll = time.monotonic()
            while not self.shutting_down:
                wait = max(0.0, next_poll - time.monotonic())
                try:
                    action, ch, val = self.commands.get(timeout=min(.25, wait))
                except queue.Empty:
                    action = 'poll'
                    ch = val = None
                if action == 'disconnect':
                    break
                if action in ('voltage', 'current', 'output'):
                    if ch not in (1, 2):
                        self.failed.emit('Invalid channel')
                        continue
                    if action == 'voltage':
                        if not (0 <= val <= 60):
                            self.failed.emit('Voltage must be 0–60 V')
                            continue
                        send(sock, f'V{ch} {val:.3f}')
                    elif action == 'current':
                        if not (0 <= val <= 20):
                            self.failed.emit('Current limit must be 0–20 A')
                            continue
                        send(sock, f'I{ch} {val:.3f}')
                    else:
                        send(sock, f'OP{ch} {int(val)}')
                    # PSU programmed readbacks can be temporarily stale.
                    # Do not report write success before matching readback.
                    ok = False
                    deadline = time.monotonic() + 2
                    while time.monotonic() < deadline and not self.shutting_down:
                        states, pending = snapshot(sock, [ch], pending)
                        actual = states[ch]
                        index = {'voltage':0, 'current':1, 'output':2}[action]
                        tolerance = .011 if index != 2 else 0
                        if abs(actual[index] - val) <= tolerance:
                            ok = True
                            break
                        time.sleep(.075)
                    if not ok and not self.shutting_down:
                        self.failed.emit(f'CH{ch} {action}: write not verified; check PSU')
                if time.monotonic() >= next_poll or action in ('voltage','current','output'):
                    states, pending = snapshot(sock, [1, 2], pending)
                    readings = {}
                    for channel in (1, 2):
                        reading, pending = measure(sock, channel, pending)
                        readings[channel] = tuple(reading)
                    self.state_changed.emit(states, readings)
                    next_poll = time.monotonic() + .25
        except Exception as exc:
            reason = f'Manual connection error: {exc}'
            self.failed.emit(reason)
        finally:
            if sock is not None:
                try:
                    # No SCPI command, including a query, follows LOCAL.
                    send(sock, 'LOCAL')
                except Exception as exc:
                    reason += f'; LOCAL failed: {exc}'
                    self.failed.emit('LOCAL failed; check instrument manually')
                sock.close()
            self.finished_safe.emit(reason)
