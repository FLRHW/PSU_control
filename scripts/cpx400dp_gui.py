#!/usr/bin/env python3
"""CPX400DP desktop GUI: offline preview + validated CLI runner frontend.

The GUI never talks to the PSU. The proven runner remains the only program
that opens the instrument socket, sends setpoints and restores output states.
"""
import os
import csv
import json
import shutil
import socket
import tempfile
import io
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from PySide6.QtCore import Qt, QProcess, QThread, Signal, QUrl, QSettings, QTimer
    from PySide6.QtGui import QDesktopServices, QPixmap, QFont
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QPlainTextEdit, QFileDialog, QScrollArea,
        QProgressBar, QMessageBox, QSplitter, QGroupBox, QFrame, QSizePolicy,
        QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit, QTabWidget, QDialog
    )
    QT_LIBRARY = 'PySide6'
except ImportError:
    try:
        from PyQt5.QtCore import Qt, QProcess, QThread, pyqtSignal as Signal, QUrl, QSettings, QTimer
        from PyQt5.QtGui import QDesktopServices, QPixmap, QFont
        from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QPlainTextEdit, QFileDialog, QScrollArea,
            QProgressBar, QMessageBox, QSplitter, QGroupBox, QFrame, QSizePolicy,
            QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit, QTabWidget, QDialog
        )
        QT_LIBRARY = 'PyQt5'
    except ImportError:
        raise SystemExit(
            'Qt bindings not installed. On Kubuntu: sudo apt install python3-pyqt5\n'
            'Then run with: /usr/bin/python3 cpx400dp_gui.py\n'
            'Alternatively install PySide6 in the Python environment you use.')

from cpx400dp_gui_core import (
    require_files, embedded_preview_plots, parse_progress, parse_report_path,
    parse_heartbeat, parse_final_verification, classify_run
)
from cpx400dp_preview import profile_summary, generate_preview
from cpx400dp_manual import ManualWorker
from cpx400dp_network_setup import (diagnose_connection, setup_ethernet_link_local,
                                     network_route_summary, instrument_route_summary)

HERE = Path(__file__).resolve().parent


class PreviewJob(QThread):
    completed = Signal(object, object, object)  # path, summary, embedded PNGs
    failed = Signal(str)

    def __init__(self, profile, output_dir=None, overrides=None, parent=None):
        super().__init__(parent)
        self.profile = Path(profile)
        self.output_dir = Path(output_dir) if output_dir is not None else None
        self.overrides = dict(overrides or {})

    def run(self):
        try:
            summary = profile_summary(self.profile, overrides=self.overrides)
            output_path = (self.output_dir / (self.profile.stem + '_preview.html')
                           if self.output_dir is not None else None)
            html_path = generate_preview(self.profile, output_path=output_path, overrides=self.overrides)
            images = embedded_preview_plots(html_path)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.completed.emit(html_path, summary, images)


class ConnectionProbeJob(QThread):
    """Read-only, asynchronous *IDN? discovery. No profile control commands."""
    completed = Signal(object)

    def __init__(self, address, interface, parent=None):
        super().__init__(parent)
        self.address = address
        self.interface = interface

    def run(self):
        try:
            result = diagnose_connection(self.address, self.interface)
        except Exception as exc:
            result = {'status': 'error', 'message': str(exc),
                      'matches': [], 'setup': []}
        self.completed.emit(result)


class AdapterSetupJob(QThread):
    """Opt-in NetworkManager profile setup; never touches the PSU itself."""
    completed = Signal(bool, str)

    def __init__(self, interface, parent=None):
        super().__init__(parent)
        self.interface = interface

    def run(self):
        try:
            profile = setup_ethernet_link_local(self.interface)
        except Exception as exc:
            self.completed.emit(False, str(exc))
            return
        self.completed.emit(True, profile)


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('CPX400DP — Profile Runner & Manual Control')
        self.resize(1150, 840)
        self.profile = None
        self.manual_worker = None
        self.manual_online = False
        self.manual_output_states = {1: None, 2: None}
        self.pause_manual_active = False
        self.pause_control_dir = None
        self.pause_socket_path = None
        self.preview_job = None
        self.connection_probe_job = None
        self.adapter_setup_job = None
        self.network_setup_candidates = []
        self.preview_path = None
        self.report_path = None
        self.process = None
        self.console_file = None
        self.console_log_path = None
        self.run_id = None
        self.running = False
        self.stopping = False
        self.paused = False
        self.output_buffer = ''
        self.success_summary = False
        self.experiment_health_failed = False
        self.run_summary = ''
        self.connection_not_established = False
        self.connection_not_established = False
        self.final_states = {}
        self.last_phase = ''
        self.measurement_log = None
        self.readback_poll_enabled = False
        self.log_offset = 0
        self.log_remainder = ''
        self.log_columns = None
        self.original_preview_pixmaps = []
        self.pending_preview_refresh = False
        self._setting_defaults = {}
        self.preview_debounce = QTimer(self)
        self.preview_debounce.setSingleShot(True)
        self.preview_debounce.setInterval(420)
        self.preview_debounce.timeout.connect(self.refresh_preview)
        self.measurement_timer = QTimer(self)
        self.measurement_timer.setInterval(250)
        self.measurement_timer.timeout.connect(self.poll_measurements)
        # QSettings uses the standard per-user configuration directory on Kubuntu.
        # Last-used folders are remembered; never persist instrument credentials.
        self.settings = QSettings('CPX400DP', 'ControlGUI')
        saved_dir = str(self.settings.value('output_directory', '') or '')
        self.saved_output_dir = Path(saved_dir).expanduser() if saved_dir and Path(saved_dir).is_dir() else None
        self.output_dir = self.saved_output_dir

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(11)

        heading = QLabel('CPX400DP — experiment control')
        heading.setStyleSheet('font-size: 21px; font-weight: 650;')
        layout.addWidget(heading)
        # Compact two-column toolbar as requested: selectors stacked at left,
        # preview buttons above profile details at right.
        toolbar = QHBoxLayout()
        selectors = QVBoxLayout()
        csv_row = QHBoxLayout()
        self.choose_btn = QPushButton('Choose CSV…')
        self.choose_btn.clicked.connect(self.choose_profile)
        csv_row.addWidget(self.choose_btn)
        self.file_label = QLabel('No profile')
        self.file_label.setMinimumWidth(90)
        self.file_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        csv_row.addWidget(self.file_label, 1)
        selectors.addLayout(csv_row)
        output_row = QHBoxLayout()
        self.output_btn = QPushButton('Output folder…')
        self.output_btn.clicked.connect(self.choose_output_directory)
        output_row.addWidget(self.output_btn)
        self.output_label = QLabel(str(self.output_dir) if self.output_dir else 'CSV folder (default)')
        self.output_label.setMinimumWidth(90)
        self.output_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        output_row.addWidget(self.output_label, 1)
        selectors.addLayout(output_row)
        # Keep routine experiment controls clear: network configuration and
        # diagnostics live in a separate nonmodal dialog. All existing
        # connection users continue reading the same widgets and values.
        self.network_settings_btn = QPushButton('Network settings…')
        self.network_settings_btn.setToolTip(
            'IP/interface, read-only PSU identification and optional adapter setup')
        self.network_settings_btn.clicked.connect(self.open_network_settings)
        self.network_dialog = QDialog(self)
        self.network_dialog.setWindowTitle('CPX400DP — Network settings')
        self.network_dialog.setMinimumWidth(680)
        self.network_dialog.resize(740, 310)
        dialog_layout = QVBoxLayout(self.network_dialog)
        dialog_layout.setContentsMargins(18, 16, 18, 14)
        dialog_layout.setSpacing(12)
        dialog_heading = QLabel('Power supply connection')
        dialog_heading.setStyleSheet('font-size: 17px; font-weight: 650;')
        dialog_layout.addWidget(dialog_heading)
        dialog_hint = QLabel(
            'Leave PSU IPv4 blank to use the profile CSV address first, then automatic discovery. '
            'Testing sends only *IDN? and closes its temporary connection.')
        dialog_hint.setWordWrap(True)
        dialog_layout.addWidget(dialog_hint)
        connection_row = QHBoxLayout()
        connection_row.addWidget(QLabel('PSU IPv4:'))
        self.psu_ip = QLineEdit()
        self.psu_ip.setPlaceholderText('CSV address / automatic discovery')
        self.psu_ip.setToolTip('Optional IPv4 override. Blank: use the profile CSV address first, then search for the PSU if needed.')
        self.psu_ip.setMinimumWidth(230)
        connection_row.addWidget(self.psu_ip, 2)
        connection_row.addWidget(QLabel('Interface:'))
        self.psu_interface = QComboBox()
        self.psu_interface.setEditable(True)
        self.psu_interface.addItem('Auto')
        try:
            from cpx400dp_discovery import interfaces
            for iface in interfaces():
                self.psu_interface.addItem(iface)
        except OSError:
            pass
        self.psu_interface.setMinimumWidth(230)
        self.psu_interface.setToolTip(
            'Optional network interface override; Auto checks active interfaces.')
        connection_row.addWidget(self.psu_interface, 2)
        dialog_layout.addLayout(connection_row)

        dialog_actions = QHBoxLayout()
        self.test_connection_btn = QPushButton('Test connection')
        self.test_connection_btn.setToolTip(
            'Read-only identification; no PSU output commands.')
        self.test_connection_btn.clicked.connect(self.test_connection)
        dialog_actions.addWidget(self.test_connection_btn)
        self.prepare_adapter_btn = QPushButton('Prepare adapter…')
        self.prepare_adapter_btn.setEnabled(False)
        self.prepare_adapter_btn.setToolTip(
            'Opt-in one-time NetworkManager link-local configuration.')
        self.prepare_adapter_btn.clicked.connect(self.prepare_adapter)
        dialog_actions.addWidget(self.prepare_adapter_btn)
        self.inspect_routes_btn = QPushButton('Inspect routes')
        self.inspect_routes_btn.setToolTip(
            'Read-only check for conflicting routes across Ethernet adapters')
        self.inspect_routes_btn.clicked.connect(self.inspect_network_routes)
        dialog_actions.addWidget(self.inspect_routes_btn)
        dialog_actions.addStretch()
        dialog_layout.addLayout(dialog_actions)

        self.connection_message = QLabel(
            'Not tested — profile execution establishes its own verified connection.')
        self.connection_message.setWordWrap(True)
        self.connection_message.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.connection_message.setMinimumHeight(55)
        self.connection_message.setStyleSheet('color: #455a70; font-size: 12px;')
        dialog_layout.addWidget(self.connection_message)
        dialog_layout.addStretch()
        bottom_actions = QHBoxLayout()
        bottom_actions.addStretch()
        close_network_btn = QPushButton('Close')
        close_network_btn.clicked.connect(self.network_dialog.hide)
        bottom_actions.addWidget(close_network_btn)
        dialog_layout.addLayout(bottom_actions)
        toolbar.addLayout(selectors, 1)

        preview_tools = QVBoxLayout()
        preview_buttons = QHBoxLayout()
        self.preview_btn = QPushButton('Refresh preview')
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self.refresh_preview)
        preview_buttons.addWidget(self.preview_btn)
        self.open_preview_btn = QPushButton('Open preview in browser')
        self.open_preview_btn.setEnabled(False)
        self.open_preview_btn.clicked.connect(lambda: self.open_file(self.preview_path))
        preview_buttons.addWidget(self.open_preview_btn)
        preview_buttons.addSpacing(12)
        preview_buttons.addWidget(QLabel('Profile'))
        self.duration_box = QLineEdit('—')
        self.duration_box.setReadOnly(True)
        self.duration_box.setAlignment(Qt.AlignCenter)
        self.duration_box.setFixedWidth(75)
        self.duration_box.setToolTip('Main profile duration (CSV keyframes; excludes initial/final ramps)')
        preview_buttons.addWidget(self.duration_box)
        preview_buttons.addSpacing(12)
        preview_buttons.addWidget(self.network_settings_btn)
        preview_buttons.addStretch()
        preview_tools.addLayout(preview_buttons)
        toolbar.addLayout(preview_tools, 2)
        layout.addLayout(toolbar)
        # Optional overrides take effect ONLY for this run; CSV stays untouched.
        overrides_bar = QHBoxLayout()
        self.override_check = QCheckBox('Select channels:')
        self.override_check.setToolTip('Enable a subset of channels already defined by the waveform CSV')
        self.override_check.toggled.connect(self.overrides_changed)
        overrides_bar.addWidget(self.override_check)
        # Channel selection lives next to Override CSV (as in the GUI sketch),
        # not in the preview toolbar. Disabled until overrides are active.
        
        self.channel_indicators = {}
        for channel in (1, 2):
            check = QCheckBox(f'Ch{channel}')
            check.setToolTip('Only CSV-defined channels can be selected; at least one must remain selected')
            check.toggled.connect(self.overrides_changed)
            self.channel_indicators[channel] = check
            overrides_bar.addWidget(check)
        self.mode_selector = QComboBox()
        self.mode_selector.addItems(['linear', 'step'])
        overrides_bar.addSpacing(14)
        overrides_bar.addWidget(QLabel('Defaults: Mode'))
        overrides_bar.addWidget(self.mode_selector)
        self.override_spins = {}
        for field, label, low, high, decimals, suffix in (
            ('interval_s', 'Steps', 0.05, 60., 3, ' s'),
            ('readback_interval_s', 'Readings', 0.10, 60., 3, ' s'),
            ('initial_ramp_s', 'Initial ramp', 0., 3600., 2, ' s'),
            ('final_ramp_s', 'Final ramp', 0., 3600., 2, ' s')):
            spin = QDoubleSpinBox()
            spin.setRange(low, high)
            spin.setDecimals(decimals)
            spin.setSingleStep(0.05 if field != 'readback_interval_s' else 0.1)
            spin.setSuffix(suffix)
            spin.setMinimumWidth(95)
            self.override_spins[field] = spin
            overrides_bar.addWidget(QLabel(label))
            overrides_bar.addWidget(spin)
            spin.valueChanged.connect(self.application_settings_changed)
        self.mode_selector.currentIndexChanged.connect(self.application_settings_changed)
        overrides_bar.addStretch()
        layout.addLayout(overrides_bar)
        self.set_override_enabled(False)
        self.load_application_defaults()

        # Run buttons, current phase, overall status, progress and both
        # readbacks/restoration statuses share one compact panel.
        readouts = QGroupBox('Experiment control and live PSU measurements')
        readout_layout = QHBoxLayout(readouts)
        left = QVBoxLayout()
        buttons = QHBoxLayout()
        self.start_btn = QPushButton('▶ Start')
        self.start_btn.setEnabled(False)
        self.start_btn.setObjectName('startButton')
        self.start_btn.clicked.connect(self.start_run)
        buttons.addWidget(self.start_btn)
        self.pause_btn = QPushButton('Ⅱ Pause')
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.toggle_pause)
        buttons.addWidget(self.pause_btn)
        self.stop_btn = QPushButton('■ Stop (restore)')
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_run)
        buttons.addWidget(self.stop_btn)
        self.reset_btn = QPushButton('Reset status')
        self.reset_btn.setToolTip('Clear GUI run status only; sends no PSU commands')
        self.reset_btn.clicked.connect(self.reset_status)
        buttons.addWidget(self.reset_btn)
        left.addLayout(buttons)
        self.status = QLabel('Idle')
        self.status.setStyleSheet('font-weight: 650;')
        left.addWidget(self.status)
        self.phase_label = QLabel('Phase: Idle')
        self.phase_label.setStyleSheet('color: #455a70;')
        left.addWidget(self.phase_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(17)
        self.progress.setFormat('%p% (estimated)')
        left.addWidget(self.progress)
        readout_layout.addLayout(left, 2)
        self.channel_labels = {}
        self.restore_labels = {}
        for ch in (1, 2):
            group = QVBoxLayout()
            title = QLabel(f'Channel {ch}')
            title.setStyleSheet('font-weight: 650;')
            values = QLabel('— V   — A')
            values.setStyleSheet('font-size: 15px; font-weight: 600;')
            restore = QLabel('Restoration: not checked')
            restore.setStyleSheet('color: #586779; font-size: 12px;')
            group.addWidget(title)
            group.addWidget(values)
            group.addWidget(restore)
            group.addStretch()
            readout_layout.addLayout(group, 1)
            self.channel_labels[ch] = values
            self.restore_labels[ch] = restore
        layout.addWidget(readouts)

        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter, 1)

        plot_group = QGroupBox('Profile preview')
        preview_layout = QVBoxLayout(plot_group)
        self.plot_area = QScrollArea()
        self.plot_area.setWidgetResizable(True)
        self.plot_container = QWidget()
        self.plots_layout = QHBoxLayout(self.plot_container)
        self.plots_layout.setSpacing(8)
        self.plots_layout.setAlignment(Qt.AlignTop)
        self.plots_layout.addWidget(QLabel('No preview generated.'))
        self.plot_area.setWidget(self.plot_container)
        preview_layout.addWidget(self.plot_area)
        shared = QHBoxLayout()
        shared.addStretch()
        for label, color in [('Voltage setpoint (V)', '#2369b7'),
                             ('Current limit (A)', '#c36918')]:
            swatch = QLabel('━━━━')
            swatch.setStyleSheet(f'color: {color}; font-size: 16px; font-weight: bold;')
            shared.addWidget(swatch)
            shared.addWidget(QLabel(label))
            shared.addSpacing(16)
        shared.addStretch()
        preview_layout.addLayout(shared)
        splitter.addWidget(plot_group)

        output_group = QGroupBox('Run output')
        output_layout = QVBoxLayout(output_group)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setLineWrapMode(QPlainTextEdit.NoWrap)
        fixed_font = QFont('Monospace')
        fixed_font.setStyleHint(QFont.TypeWriter)
        self.console.setFont(fixed_font)
        self.console.setMaximumBlockCount(5000)
        output_layout.addWidget(self.console)
        footer = QHBoxLayout()
        self.report_btn = QPushButton('Open latest report')
        self.report_btn.setEnabled(False)
        self.report_btn.clicked.connect(lambda: self.open_file(self.report_path))
        footer.addWidget(self.report_btn)
        footer.addStretch()
        clear_btn = QPushButton('Clear console')
        clear_btn.clicked.connect(self.console.clear)
        footer.addWidget(clear_btn)
        output_layout.addLayout(footer)
        splitter.addWidget(output_group)
        splitter.setSizes([540, 140])

        # Manual mode uses a dedicated network worker. No profile runner may
        # start while that worker holds the instrument connection.
        self.tabs = QTabWidget()
        self.tabs.addTab(root, 'Profile Runner')
        self.manual_tab = QWidget()
        self.tabs.addTab(self.manual_tab, 'Manual Control')
        self.setCentralWidget(self.tabs)
        self.build_manual_tab()

        self.setStyleSheet('''
            QMainWindow { background: #f7f9fc; }
            QGroupBox { border: 1px solid #d3dce8; border-radius: 8px;
                        margin-top: 10px; padding-top: 12px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { padding: 7px 12px; border: 1px solid #aabbcf;
                          border-radius: 6px; background: white; }
            QPushButton:hover:enabled { background: #eaf2fc; }
            QPushButton:disabled { color: #8490a1; background: #f1f3f6; }
            QPushButton#startButton:enabled { background: #dff4e7; border-color: #8abda0; }
            QPlainTextEdit, QScrollArea { background: white; border: 1px solid #d3dce8; }
        ''')

    def build_manual_tab(self):
        layout = QVBoxLayout(self.manual_tab)
        layout.setSpacing(14)
        top = QHBoxLayout()
        top.addWidget(QLabel('Manual control — Basic V / I / Output'))
        self.manual_connect_btn = QPushButton('Connect to PSU')
        self.manual_connect_btn.clicked.connect(self.connect_manual)
        top.addWidget(self.manual_connect_btn)
        self.manual_disconnect_btn = QPushButton('Disconnect (LOCAL)')
        self.manual_disconnect_btn.setEnabled(False)
        self.manual_disconnect_btn.clicked.connect(self.disconnect_manual)
        top.addWidget(self.manual_disconnect_btn)
        self.manual_resume_btn = QPushButton('Resume paused profile')
        self.manual_resume_btn.setEnabled(False)
        self.manual_resume_btn.clicked.connect(self.toggle_pause)
        top.addWidget(self.manual_resume_btn)
        top.addStretch()
        layout.addLayout(top)
        self.manual_status = QLabel('Disconnected — outputs are not controlled')
        layout.addWidget(self.manual_status)
        self.manual_cards = {}
        cards = QHBoxLayout()
        for ch in (1, 2):
            panel = QGroupBox(f'Channel {ch}')
            fields = QVBoxLayout(panel)
            meter = QLabel('Measured: — V    — A')
            meter.setStyleSheet('font-size: 19px; font-weight: 600;')
            fields.addWidget(meter)
            state = QLabel('Programmed: — V / — A')
            fields.addWidget(state)
            output_badge = QLabel('OUTPUT UNKNOWN')
            output_badge.setAlignment(Qt.AlignCenter)
            output_badge.setObjectName('outputIndicator')
            output_badge.setStyleSheet('font-size: 16px; font-weight: 700; padding: 9px; '
                                       'border-radius: 6px; color: #465365; background: #e3e9f1;')
            fields.addWidget(output_badge)
            regulation = QLabel('REGULATION: UNKNOWN')
            regulation.setToolTip('Last unambiguous CV/CC/UNREG event from the read-and-clear LSR register; not a guaranteed live operating-mode reading.')
            regulation.setStyleSheet('font-size: 13px; font-weight: 600; color: #536173;')
            fields.addWidget(regulation)
            self.manual_cards[(ch, 'regulation')] = regulation
            for key, name, low, high in (
                ('voltage', 'Voltage (V)', 0, 60),
                ('current', 'Current limit (A)', 0, 20)):
                row = QHBoxLayout()
                row.addWidget(QLabel(name))
                spin = QDoubleSpinBox()
                spin.setRange(low,high)
                spin.setDecimals(2)
                spin.setSingleStep(.1)
                row.addWidget(spin)
                apply = QPushButton('Apply')
                apply.setEnabled(False)
                apply.clicked.connect(lambda _, c=ch, k=key, x=spin: self.manual_send(k, c, x.value()))
                row.addWidget(apply)
                fields.addLayout(row)
                self.manual_cards[(ch,key)] = (spin, apply)
            on = QPushButton('Enable output')
            off = QPushButton('Disable output')
            on.setEnabled(False)
            off.setEnabled(False)
            on.clicked.connect(lambda _, c=ch: self.manual_send('output',c,1))
            off.clicked.connect(lambda _, c=ch: self.manual_send('output',c,0))
            row = QHBoxLayout()
            row.addWidget(on)
            row.addWidget(off)
            fields.addLayout(row)
            self.manual_cards[ch] = (meter, state, on, off, output_badge)
            cards.addWidget(panel)
        layout.addLayout(cards)
        layout.addWidget(QLabel('Standalone: changes stay programmed after Disconnect (LOCAL). '
                                'During a paused profile: changes are temporary; Resume restores '
                                'and verifies the pause-point settings before continuing.'))
        layout.addStretch()

    def manual_widgets_enabled(self, enabled):
        for ch in (1,2):
            for key in ('voltage','current'):
                self.manual_cards[(ch,key)][1].setEnabled(enabled and
                    (not self.pause_manual_active or ch in self.run_channels))
            allowed = enabled and (not self.pause_manual_active or ch in self.run_channels)
            output_state = self.manual_output_states[ch]
            self.manual_cards[ch][2].setEnabled(allowed and output_state is False)
            self.manual_cards[ch][3].setEnabled(allowed and output_state is True)
        self.manual_disconnect_btn.setEnabled(enabled)
        self.manual_resume_btn.setEnabled(self.running and self.paused and not self.stopping)

    def connect_manual(self):
        if self.running:
            if not (self.paused and not self.stopping and self.pause_socket_path):
                return
            # A paused runner owns the only PSU TCP connection; this merely
            # enables controls which issue local IPC requests to that runner.
            self.pause_manual_active = True
            self.manual_online = True
            # Paused runner controls the existing socket; LSR event polling
            # will be handled separately, never by an extra ManualWorker.
            self.manual_regulation_update({1: None, 2: None})
            self.manual_connect_btn.setEnabled(False)
            self.manual_disconnect_btn.setText('Leave paused controls')
            self.manual_status.setText('PAUSED PROFILE — temporary manual control. '
                'Resume restores held profile settings before profile time advances.')
            self.manual_widgets_enabled(True)
            self.tabs.setCurrentWidget(self.manual_tab)
            return
        if self.manual_worker is not None:
            return
        address = self.psu_ip.text().strip()
        if not address and self.profile:
            try:
                with self.profile.open(encoding='utf-8-sig') as source:
                    for line in source:
                        if not line.lstrip().startswith('#'):
                            break
                        key, sep, value = line.lstrip()[1:].strip().partition('=')
                        if sep and key.strip() == 'host':
                            address = value.rstrip(',').strip()
                            break
            except OSError:
                pass
        address = address or '169.254.51.7'
        interface = self.psu_interface.currentText().strip()
        interface = None if not interface or interface == 'Auto' else interface
        self.manual_status.setText('Connecting; verifying initial programmed states…')
        self.manual_connect_btn.setEnabled(False)
        self.test_connection_btn.setEnabled(False)
        self.prepare_adapter_btn.setEnabled(False)
        self.manual_output_states = {1: None, 2: None}
        self.manual_regulation_update({1: None, 2: None})
        self.start_btn.setEnabled(False)
        self.choose_btn.setEnabled(False)
        self.override_check.setEnabled(False)
        self.set_override_enabled(False)
        self.manual_worker = ManualWorker(address, interface, self)
        self.manual_worker.connected.connect(self.manual_connected)
        self.manual_worker.state_changed.connect(self.manual_update)
        self.manual_worker.regulation_changed.connect(self.manual_regulation_update)
        self.manual_worker.failed.connect(self.manual_error)
        self.manual_worker.finished_safe.connect(self.manual_done)
        self.manual_worker.start()

    def manual_connected(self, description):
        self.manual_online = True
        self.manual_status.setText('Connected — ' + description)
        self.manual_widgets_enabled(True)

    def manual_update(self, programmed, readings):
        for ch in (1,2):
            if ch in programmed:
                v, a, enabled = programmed[ch]
                meter, state, on, off, indicator = self.manual_cards[ch]
                self.manual_output_states[ch] = bool(enabled)
                state.setText(f'Programmed: {v:.2f} V / {a:.2f} A')
                if enabled:
                    indicator.setText('● OUTPUT ON')
                    indicator.setStyleSheet('font-size: 16px; font-weight: 700; padding: 9px; '
                                            'border-radius: 6px; color: #116037; background: #ccf2dd;')
                else:
                    indicator.setText('○ OUTPUT OFF')
                    indicator.setStyleSheet('font-size: 16px; font-weight: 700; padding: 9px; '
                                            'border-radius: 6px; color: #6b2730; background: #f8dfe3;')
                # Initial readbacks populate editable values; later polling
                # never overwrites a user's pending edit.
                if not hasattr(self,'_manual_populated'):
                    self._manual_populated = set()
                if ch not in self._manual_populated:
                    self.manual_cards[(ch,'voltage')][0].setValue(v)
                    self.manual_cards[(ch,'current')][0].setValue(a)
                    self._manual_populated.add(ch)
            if ch in readings:
                voltage, current = readings[ch]
                self.manual_cards[ch][0].setText(f'Measured: {voltage:.2f} V    {current:.2f} A')
        self.manual_widgets_enabled(self.manual_online)

    def manual_regulation_update(self, modes):
        # These are *last observed events*, not continuous-state telemetry.
        colours = {'CV': '#116037', 'CC': '#854a12', 'UNREG': '#a62735', 'FAULT': '#a62735'}
        for ch in (1, 2):
            label = self.manual_cards.get((ch, 'regulation'))
            if label is None:
                continue
            mode = modes.get(ch)
            if mode in colours:
                label.setText(f'REGULATION: {mode} (last event)')
                label.setStyleSheet(f'font-size: 13px; font-weight: 600; color: {colours[mode]};')
            else:
                label.setText('REGULATION: UNKNOWN')
                label.setStyleSheet('font-size: 13px; font-weight: 600; color: #536173;')

    def manual_send(self, action, channel, value):
        if not self.manual_online:
            return
        if self.pause_manual_active and (not self.paused or not self.running or
                                         self.stopping or channel not in self.run_channels):
            return
        if not self.pause_manual_active and not self.manual_worker:
            return
        if action == 'output' and self.manual_output_states[channel] is not None \
                and bool(value) == self.manual_output_states[channel]:
            return  # Already in the verified output state.
        if self.pause_manual_active:
            self.send_pause_manual_command(action, channel, value)
        else:
            self.manual_worker.request(action, channel, value)

    def send_pause_manual_command(self, action, channel, value):
        if not self.pause_manual_active or not self.pause_socket_path or not self.paused:
            return
        try:
            raw = json.dumps({'action': action, 'channel': channel, 'value': value}).encode()
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
                client.sendto(raw, self.pause_socket_path)
            # Ordinary command progress/verification stays in the console; the
            # status label is reserved for mode/connection state and errors.
        except OSError as exc:
            self.manual_status.setText(f'Paused manual request failed: {exc}')
            self.append_console('GUI: Paused manual request failed: ' + str(exc))

    def disconnect_manual(self):
        if self.pause_manual_active:
            self.pause_manual_active = False
            self.manual_online = False
            self.manual_widgets_enabled(False)
            self.manual_disconnect_btn.setText('Disconnect (LOCAL)')
            self.manual_status.setText('Paused manual controls closed. Changes remain until Resume; '
                'Resume restores the held profile state.')
            self.manual_connect_btn.setEnabled(bool(self.running and self.paused and not self.stopping))
            return
        if not self.manual_worker:
            return
        self.manual_status.setText('Disconnecting; sending LOCAL as final command…')
        self.manual_widgets_enabled(False)
        self.manual_worker.request('disconnect')

    def manual_error(self, message):
        self.manual_status.setText('WARNING — ' + message)
        self.append_console('MANUAL: ' + message)

    def manual_done(self, message):
        self.manual_online = False
        self.manual_status.setText(message)
        self.manual_widgets_enabled(False)
        self.manual_connect_btn.setEnabled(True)
        self.test_connection_btn.setEnabled(True)
        self.prepare_adapter_btn.setEnabled(bool(self.network_setup_candidates))
        self.choose_btn.setEnabled(True)
        self.override_check.setEnabled(True)
        self.set_override_enabled(self.override_check.isChecked())
        self.start_btn.setEnabled(bool(self.profile) and self.preview_path is not None)
        if self.manual_worker:
            self.manual_worker.wait(1000)
            self.manual_worker.deleteLater()
            self.manual_worker = None
        self._manual_populated = set()

    def set_override_enabled(self, enabled):
        for ch, check in self.channel_indicators.items():
            check.setEnabled(enabled and ch in self._setting_defaults.get('channels', []))
        # Application defaults are independent of channel subset selection.
        self.mode_selector.setEnabled(not self.running)
        for spin in self.override_spins.values():
            spin.setEnabled(not self.running)

    def active_overrides(self):
        # App configuration always determines runtime settings, irrespective of
        # the legacy CSV header. Only channel selection uses the checkbox.
        opts = {'mode': self.mode_selector.currentText(),
                **{key: spin.value() for key, spin in self.override_spins.items()}}
        if self.override_check.isChecked():
            chosen = [ch for ch, check in self.channel_indicators.items() if check.isChecked()]
            opts['channels'] = ','.join(map(str, chosen))
        return opts

    def load_application_defaults(self):
        defaults = {'mode':'linear', 'interval_s':0.05,
                    'readback_interval_s':0.25, 'initial_ramp_s':0.0,
                    'final_ramp_s':2.0}
        self.mode_selector.blockSignals(True)
        self.mode_selector.setCurrentText(str(self.settings.value('default_mode', defaults['mode'])))
        self.mode_selector.blockSignals(False)
        for key, spin in self.override_spins.items():
            spin.blockSignals(True)
            try:
                spin.setValue(float(self.settings.value('default_' + key, defaults[key])))
            except (TypeError, ValueError):
                spin.setValue(defaults[key])
            spin.blockSignals(False)

    def application_settings_changed(self, *args):
        if self.running:
            return
        self.settings.setValue('default_mode', self.mode_selector.currentText())
        for key, spin in self.override_spins.items():
            self.settings.setValue('default_' + key, spin.value())
        if self.profile:
            self.clear_previous_run_display()
            self.preview_debounce.start()

    def sync_defaults_from_csv(self):
        try:
            settings = profile_summary(self.profile)
        except (ValueError, OSError, KeyError) as exc:
            self.append_console('PROFILE ERROR: ' + str(exc))
            return
        self._setting_defaults['channels'] = list(settings['channels'])
        for ch, check in self.channel_indicators.items():
            check.blockSignals(True)
            check.setChecked(ch in settings['channels'])
            check.blockSignals(False)
        # Channel defaults come from the CSV; persistent runtime settings
        # must not be reset when another waveform file is opened.

    def overrides_changed(self, *args):
        # Changing channel selection does not change application defaults.
        if not self.override_check.isChecked() and self.profile is not None:
            self.sync_defaults_from_csv()
        if self.override_check.isChecked() and self.profile is not None:
            if not any(check.isChecked() for check in self.channel_indicators.values()):
                # A disabled channel isn't a valid experiment. Keep the other
                # CSV-defined channel active when one is unchecked.
                selected = self.sender()
                if selected in self.channel_indicators.values():
                    selected.blockSignals(True)
                    selected.setChecked(True)
                    selected.blockSignals(False)
        self.set_override_enabled(self.override_check.isChecked() and not self.running)
        if self.profile and not self.running:
            self.clear_previous_run_display()
            self.preview_debounce.start()

    def inspect_network_routes(self):
        # A read-only, bounded local iproute2 query; no PSU socket or
        # NetworkManager modifications. Keep hardware sessions undisturbed.
        if (self.running or self.manual_worker is not None or
            (self.connection_probe_job and self.connection_probe_job.isRunning()) or
            (self.adapter_setup_job and self.adapter_setup_job.isRunning())):
            return
        try:
            result = network_route_summary()
            # Show the actual kernel decision for the known PSU address, not
            # merely whether broad /16 routes overlap. Read-only.
            host = self.psu_ip.text().strip()
            if host:
                interface = self.psu_interface.currentText().strip()
                expected = None if interface in ('', 'Auto') else interface
                result += '\n' + instrument_route_summary(host, expected)
        except (OSError, ValueError) as exc:
            result = 'Unable to inspect IPv4 routes: ' + str(exc)
        self.connection_message.setText(result)

    def open_network_settings(self):
        # Nonmodal: no extra instrument socket, no discovery on opening.
        # Running/manual ownership still disables Test/Prepare controls.
        self.network_dialog.show()

    def choose_profile(self):
        saved = Path(str(self.settings.value('last_profile_directory', '') or '')).expanduser()
        first_use = HERE.parent / 'profiles'
        start = self.profile.parent if self.profile else (
            saved if saved.is_dir() else first_use if first_use.is_dir() else Path.home())
        start_dir = str(start)
        filename, _ = QFileDialog.getOpenFileName(self, 'Choose a CPX400DP CSV profile',
                                                  start_dir, 'CSV profiles (*.csv);;All files (*)')
        if filename:
            self.load_profile(Path(filename))

    def test_connection(self):
        # Never open even a short-lived diagnostic socket while another GUI
        # activity owns the instrument connection.
        if (self.running or self.manual_worker is not None or
            self.pause_manual_active or
            (self.connection_probe_job and self.connection_probe_job.isRunning()) or
            (self.adapter_setup_job and self.adapter_setup_job.isRunning())):
            return
        host = self.psu_ip.text().strip() or None
        iface = self.psu_interface.currentText().strip()
        iface = None if iface in ('', 'Auto') else iface
        self.test_connection_btn.setEnabled(False)
        self.prepare_adapter_btn.setEnabled(False)
        self.manual_connect_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.connection_message.setText('Searching Ethernet adapters (read-only; no output commands)…')
        self.connection_probe_job = ConnectionProbeJob(host, iface, self)
        self.connection_probe_job.completed.connect(self.connection_test_finished)
        self.connection_probe_job.finished.connect(self.connection_probe_done)
        self.connection_probe_job.start()

    def connection_test_finished(self, result):
        self.test_connection_btn.setEnabled(not self.running and self.manual_worker is None)
        self.manual_connect_btn.setEnabled(not self.running and self.manual_worker is None)
        self.start_btn.setEnabled(bool(self.profile and self.preview_path) and
                                  not self.running and self.manual_worker is None)
        self.network_setup_candidates = list(result.get('setup', []))
        self.prepare_adapter_btn.setEnabled(bool(self.network_setup_candidates))
        self.connection_message.setText(result.get('message', 'No connection result'))
        if result.get('status') == 'found':
            host, iface, identity = result['matches'][0]
            self.psu_ip.setText(host)
            if self.psu_interface.findText(iface) < 0:
                self.psu_interface.addItem(iface)
            self.psu_interface.setCurrentText(iface)
            self.connection_message.setText(f'✓ Identified {identity} at {host} via {iface}. '
                                            'Test socket closed; profile not started.')
        elif result.get('status') == 'multiple':
            self.connection_message.setText(result['message'] + ' ' +
                                            '; '.join(f'{h} via {nic}' for h, nic, _ in result['matches']))
    def connection_probe_done(self):
        job = self.connection_probe_job
        self.connection_probe_job = None
        if job is not None:
            job.deleteLater()

    def prepare_adapter(self):
        if (self.running or self.manual_worker is not None or self.pause_manual_active or
            (self.adapter_setup_job and self.adapter_setup_job.isRunning()) or
            not self.network_setup_candidates):
            return
        candidates = self.network_setup_candidates
        selected = self.psu_interface.currentText().strip()
        if selected not in candidates:
            if len(candidates) != 1:
                QMessageBox.information(
                    self, 'Choose an adapter',
                    'More than one unconfigured Ethernet adapter was detected. '
                    'Select the correct interface in the Interface field and try again.')
                return
            selected = candidates[0]
        answer = QMessageBox.question(
            self, 'Prepare Ethernet adapter?',
            f'Configure {selected} with a dedicated automatic link-local IPv4 '
            'connection through NetworkManager?\n\n'
            'This changes the computer’s configuration, not the PSU. '
            'It will create a persistent CPX400DP-specific connection. '
            'NetworkManager may request your system password.\n\n'
            'The action is refused if the adapter already has an IPv4 address '
            'or an active NetworkManager connection. Other adapters are untouched.',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        self.prepare_adapter_btn.setEnabled(False)
        self.test_connection_btn.setEnabled(False)
        self.manual_connect_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.connection_message.setText(f'Preparing {selected} with NetworkManager…')
        self.adapter_setup_job = AdapterSetupJob(selected, self)
        self.adapter_setup_job.completed.connect(self.adapter_setup_finished)
        self.adapter_setup_job.finished.connect(self.adapter_setup_done)
        self.adapter_setup_job.start()

    def adapter_setup_finished(self, success, detail):
        self.test_connection_btn.setEnabled(True)
        self.manual_connect_btn.setEnabled(not self.running and self.manual_worker is None)
        self.start_btn.setEnabled(bool(self.profile and self.preview_path) and not self.running)
        if success:
            self.network_setup_candidates = []
            self.prepare_adapter_btn.setEnabled(False)
            self.connection_message.setText(
                f'NetworkManager configured {detail}. The instrument may need '
                'approximately 30 seconds to finish Auto-IP setup. '
                'Click Test connection again to identify it.')
            try:
                from cpx400dp_discovery import interfaces
                for iface in interfaces():
                    if self.psu_interface.findText(iface) < 0:
                        self.psu_interface.addItem(iface)
            except OSError:
                pass
        else:
            self.connection_message.setText('Adapter setup failed or was declined: ' + detail)
            self.prepare_adapter_btn.setEnabled(bool(self.network_setup_candidates))
    def adapter_setup_done(self):
        job = self.adapter_setup_job
        self.adapter_setup_job = None
        if job is not None:
            job.deleteLater()

    def choose_output_directory(self):
        if self.running or (self.preview_job and self.preview_job.isRunning()):
            return
        start = self.output_dir or (self.profile.parent if self.profile else Path.home() / 'Downloads')
        folder = QFileDialog.getExistingDirectory(self, 'Choose measurement/report output folder', str(start))
        if folder:
            self.output_dir = Path(folder).resolve()
            self.output_label.setText(self.output_dir.name)
            self.output_label.setToolTip(str(self.output_dir))
            self.settings.setValue('output_directory', str(self.output_dir))
            self.settings.sync()
            if self.profile is not None:
                self.refresh_preview()

    def load_profile(self, path):
        if self.running or (self.preview_job and self.preview_job.isRunning()):
            return
        self.profile = Path(path).resolve()
        self.settings.setValue('last_profile_directory', str(self.profile.parent))
        self.settings.sync()
        # A newly selected profile must never inherit the previous run's
        # measurements, restoration badges, or completed progress indicator.
        self.clear_previous_run_display()
        # Switching profiles must not retain edits from another CSV.
        self.override_check.blockSignals(True)
        self.override_check.setChecked(False)
        self.override_check.blockSignals(False)
        self.set_override_enabled(False)
        self.sync_defaults_from_csv()
        self.set_channel_status_idle()
        self.file_label.setText(self.profile.name)
        self.file_label.setToolTip(str(self.profile))
        if self.output_dir is None:
            self.output_label.setText(self.profile.parent.name + ' (default)')
            self.output_label.setToolTip(str(self.profile.parent))
        self.start_btn.setEnabled(False)
        self.report_btn.setEnabled(False)
        self.report_path = None
        self.preview_path = None
        self.open_preview_btn.setEnabled(False)
        self.refresh_preview()

    def refresh_preview(self):
        if not self.profile or self.running:
            return
        if self.preview_job is not None and self.preview_job.isRunning():
            self.pending_preview_refresh = True
            return
        self.pending_preview_refresh = False
        self.preview_btn.setEnabled(False)
        self.choose_btn.setEnabled(False)
        self.output_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.status.setText('Generating offline preview…')
        self.status.setText('Previewing (no PSU connection)')
        job = PreviewJob(self.profile, self.output_dir, self.active_overrides(), self)
        self.preview_job = job
        job.completed.connect(self.preview_ready)
        job.failed.connect(self.preview_failed)
        job.finished.connect(self.preview_finished)
        job.start()

    def preview_finished(self):
        if self.pending_preview_refresh and not self.running:
            self.pending_preview_refresh = False
            self.preview_debounce.start(10)
        self.preview_btn.setEnabled(bool(self.profile) and not self.running)
        self.choose_btn.setEnabled(not self.running)
        self.output_btn.setEnabled(not self.running)

    def preview_failed(self, message):
        self.status.setText('Preview error')
        self.append_console(f'PREVIEW ERROR: {message}')
        self.start_btn.setEnabled(False)
        self.append_console(f'PREVIEW ERROR: {message}')

    def preview_ready(self, output_path, info, images):
        self.preview_path = Path(output_path)
        self.open_preview_btn.setEnabled(True)
        self.duration_box.setText(f'{info["duration_s"]:g} s')
        # Channel boxes are editable overrides: do not reset them from the
        # preview result, which may be stale while a new preview is pending.
        self.clear_plots()
        self.original_preview_pixmaps = []
        for title, blob in images:
            original = QPixmap()
            if original.loadFromData(blob, 'PNG'):
                self.original_preview_pixmaps.append((title, original))
        self.display_preview_pixmaps()
        self.status.setText('Ready — preview calculated locally')
        self.start_btn.setEnabled(self.manual_worker is None)

    def display_preview_pixmaps(self):
        """Fit 1 or 2 original 6.8:3.6 charts without enlarging single-channel plots.

        Preserve the complete image (including lower time-axis ticks); never
        crop the pixmap. The scroll area handles exceptionally narrow windows.
        """
        self.clear_plots()
        if not self.original_preview_pixmaps:
            return
        count = len(self.original_preview_pixmaps)
        available = max(240, self.plot_area.viewport().width() - 32)
        # Two graphs may share the full width, but a sole chart stays at the
        # same sensible size instead of expanding to fill a wide GUI window.
        width = min(650, max(260, (available - 12 * (count - 1)) // count))
        if count == 1:
            self.plots_layout.addStretch(1)
        for title, original in self.original_preview_pixmaps:
            block = QWidget()
            block.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            block_layout = QVBoxLayout(block)
            block_layout.setContentsMargins(1, 1, 1, 1)
            heading = QLabel(title.split(' voltage')[0])
            heading.setStyleSheet('font-weight: 650;')
            block_layout.addWidget(heading)
            picture = QLabel()
            picture.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            scaled = original.scaled(width, 350, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            picture.setPixmap(scaled)
            picture.setFixedSize(scaled.size())
            block_layout.addWidget(picture)
            self.plots_layout.addWidget(block)
        if count == 1:
            self.plots_layout.addStretch(1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.original_preview_pixmaps:
            current_width = self.plot_area.viewport().width()
            if not hasattr(self, '_preview_width') or abs(current_width - self._preview_width) > 35:
                self._preview_width = current_width
                self.display_preview_pixmaps()

    def poll_measurements(self):
        """Read appended CSV rows only; never contacts the PSU."""
        if not self.readback_poll_enabled or not self.measurement_log:
            return
        try:
            with self.measurement_log.open('r', encoding='utf-8', newline='') as handle:
                if handle.seek(0, 2) < self.log_offset:
                    self.log_offset = 0
                    self.log_remainder = ''
                    self.log_columns = None
                handle.seek(self.log_offset)
                data = handle.read()
                self.log_offset = handle.tell()
        except (FileNotFoundError, OSError):
            return
        if not data:
            return
        raw = self.log_remainder + data
        lines = raw.split('\n')
        self.log_remainder = lines.pop()
        for line in lines:
            if not line.strip():
                continue
            try:
                fields = next(csv.reader([line]))
                if self.log_columns is None:
                    if 'event' in fields and 'measured_voltage_v' in fields:
                        self.log_columns = {key: idx for idx, key in enumerate(fields)}
                    continue
                col = self.log_columns
                if fields[col['event']] != 'readback':
                    continue
                ch = int(fields[col['channel']])
                if ch not in self.channel_labels:
                    continue
                v = float(fields[col['measured_voltage_v']])
                a = float(fields[col['measured_current_a']])
                self.channel_labels[ch].setText(f'{v:.2f} V   {a:.2f} A')
            except (ValueError, IndexError, csv.Error, KeyError):
                continue

    def clear_plots(self):
        while self.plots_layout.count():
            child = self.plots_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def displayed_channels(self):
        """Effective selected channels for status labels; no PSU I/O."""
        csv_channels = set(self._setting_defaults.get('channels', []))
        if self.override_check.isChecked():
            return {ch for ch in csv_channels if self.channel_indicators[ch].isChecked()}
        return csv_channels

    def set_channel_status_idle(self):
        """Distinguish excluded channels from selected, unverified channels."""
        selected = self.displayed_channels()
        for ch in (1, 2):
            self.channel_labels[ch].setText('— V   — A')
            label = self.restore_labels[ch]
            label.setText('Restoration: not checked' if ch in selected else
                          'N/A — channel not selected')
            label.setStyleSheet('color: #586779; font-size: 12px;')

    def clear_previous_run_display(self):
        """Invalidate the *display* of a previous run after an idle edit.

        This never sends SCPI commands, touches saved run files, or discards
        the console history. It prevents stale polling from repainting the
        readouts while a new profile preview is being generated.
        """
        if self.running or (self.process is not None and
                            self.process.state() != QProcess.NotRunning):
            return
        self.measurement_timer.stop()
        self.readback_poll_enabled = False
        self.measurement_log = None
        self.log_offset = 0
        self.log_remainder = ''
        self.log_columns = None
        self.progress.setValue(0)
        self.phase_label.setText('Phase: Idle')
        self.run_summary = ''
        self.success_summary = False
        self.experiment_health_failed = False
        self.final_states = {}
        self.last_phase = ''
        self.report_path = None
        self.report_btn.setEnabled(False)
        self.set_channel_status_idle()
        self.status.setText('Ready — profile settings changed; no PSU state checked')

    def reset_status(self):
        """Clear displayed status without changing any instrument settings."""
        if self.running or (self.process is not None and
                            self.process.state() != QProcess.NotRunning):
            return
        self.status.setText('Ready — status cleared (PSU state not checked)')
        self.phase_label.setText('Phase: Idle')
        self.progress.setValue(0)
        self.run_summary = ''
        self.success_summary = False
        self.final_states = {}
        self.set_channel_status_idle()
        self.append_console('GUI: Run status reset (no PSU commands sent).')

    def append_console(self, line):
        self.console.appendPlainText(line)
        if self.console_file is not None:
            try:
                self.console_file.write(line + '\n')
                self.console_file.flush()
            except OSError as exc:
                self.console_file.close()
                self.console_file = None
                self.status.setText(f'Console log write error: {exc}')

    def close_console_log(self):
        if self.console_file is not None:
            self.console_file.flush()
            self.console_file.close()
            self.console_file = None

    def cleanup_pause_control(self):
        if self.pause_control_dir:
            shutil.rmtree(self.pause_control_dir, ignore_errors=True)
            self.pause_control_dir = None
            self.pause_socket_path = None

    def start_run(self):
        if (self.running or not self.profile or self.manual_worker is not None or
            (self.connection_probe_job and self.connection_probe_job.isRunning()) or
            (self.adapter_setup_job and self.adapter_setup_job.isRunning())):
            return
        try:
            require_files(HERE)
            profile_summary(self.profile, overrides=self.active_overrides())  # Validate effective values.
        except Exception as exc:
            QMessageBox.critical(self, 'Cannot start', str(exc))
            self.start_btn.setEnabled(False)
            return
        if self.output_dir is not None and not self.output_dir.is_dir():
            QMessageBox.critical(self, 'Invalid output directory',
                                 f'Output folder does not exist: {self.output_dir}')
            return
        self.report_path = None
        self.report_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        self.success_summary = False
        self.experiment_health_failed = False
        self.run_summary = ''
        self.final_states = {}
        self.last_phase = ''
        self.run_channels = set(profile_summary(self.profile, overrides=self.active_overrides())['channels'])
        for ch in (1, 2):
            self.channel_labels[ch].setText('— V     — A')
            self.restore_labels[ch].setText('Restoration: pending' if ch in self.run_channels
                                            else 'N/A — channel not selected')
            self.restore_labels[ch].setStyleSheet('color: #586779;')
        self.phase_label.setText('Phase: Starting')
        self.output_buffer = ''
        self.close_console_log()
        self.console.clear()
        self.run_id = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        folder = self.output_dir or self.profile.parent
        self.console_log_path = folder / f'{self.profile.stem}_console_{self.run_id}.log'
        try:
            self.console_file = self.console_log_path.open('x', encoding='utf-8', buffering=1)
        except OSError as exc:
            QMessageBox.critical(self, 'Cannot save console log', str(exc))
            self.start_btn.setEnabled(True)
            self.reset_btn.setEnabled(True)
            return
        self.measurement_log = None
        self.readback_poll_enabled = False
        self.log_offset = 0
        self.log_remainder = ''
        self.log_columns = None
        self.measurement_timer.start()
        self.progress.setValue(0)
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(self.profile.parent))
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.consume_output)
        self.process.finished.connect(self.run_finished)
        self.process.errorOccurred.connect(self.process_error)
        # -u makes terminal progress and readbacks visible immediately.
        arguments = ['-u', str(HERE / 'cpx400dp_run_enhanced.py'), str(self.profile), '--run-id', self.run_id]
        if self.output_dir is not None:
            arguments.extend(['--output-dir', str(self.output_dir)])
        ip_override = self.psu_ip.text().strip()
        interface_override = self.psu_interface.currentText().strip()
        if ip_override:
            arguments.extend(['--psu-ip', ip_override])
        if interface_override and interface_override != 'Auto':
            arguments.extend(['--psu-interface', interface_override])
        for key, value in self.active_overrides().items():
            arguments.extend(['--' + key.replace('_', '-'), str(value)])
        self.cleanup_pause_control()
        self.pause_control_dir = tempfile.mkdtemp(prefix='cpxpause-')
        self.pause_socket_path = os.path.join(self.pause_control_dir, 'control.sock')
        arguments.extend(['--pause-control-socket', self.pause_socket_path])
        self.process.start(sys.executable, arguments)
        self.running = True
        self.manual_connect_btn.setEnabled(False)
        self.test_connection_btn.setEnabled(False)
        self.prepare_adapter_btn.setEnabled(False)
        self.pause_manual_active = False
        self.stopping = False
        self.paused = False
        self.start_btn.setEnabled(False)
        # SIGUSR1 must not be sent until the runner confirms its handler is installed.
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText('Ⅱ Pause')
        self.stop_btn.setEnabled(True)
        self.choose_btn.setEnabled(False)
        self.output_btn.setEnabled(False)
        self.override_check.setEnabled(False)
        self.set_override_enabled(False)
        self.preview_btn.setEnabled(False)
        self.open_preview_btn.setEnabled(False)
        self.status.setText('Starting runner…')
        self.append_console('$ ' + sys.executable + ' ' + ' '.join(f'"{x}"' for x in arguments))
        self.append_console('GUI: Console log: ' + str(self.console_log_path))

    def consume_output(self):
        if self.process is None:
            return
        chunk = bytes(self.process.readAllStandardOutput()).decode('utf-8', 'replace')
        self.output_buffer += chunk
        while '\n' in self.output_buffer:
            line, self.output_buffer = self.output_buffer.split('\n', 1)
            self.handle_line(line.rstrip('\r'))

    def handle_line(self, line):
        self.append_console(line)
        if line.startswith('[CONNECTION NOT ESTABLISHED]'):
            self.connection_not_established = True
            self.status.setText('PSU connection failed — profile not started')
            self.phase_label.setText('Phase: Connection failed — no profile commands')
        if line.startswith('[PAUSE MANUAL STATE] '):
            try:
                data = json.loads(line.partition('] ')[2])
                programmed = {int(k): tuple(v['programmed']) for k,v in data.items()}
                readings = {int(k): tuple(v['measured']) for k,v in data.items()}
                self.manual_update(programmed, readings)
                if any('regulation' in value for value in data.values()):
                    modes = {int(k): v.get('regulation') for k, v in data.items()}
                    self.manual_regulation_update(modes)
            except (ValueError, KeyError, TypeError) as exc:
                self.append_console('GUI: Ignored malformed paused state: ' + str(exc))
        elif line.startswith('[PAUSE MANUAL OK]'):
            # Verification is already written to the runner console. Avoid
            # duplicating success messages in the Manual Control status line.
            pass
        elif line.startswith('[PAUSE MANUAL ERROR]'):
            self.manual_status.setText('WARNING: ' + line.partition('] ')[2])
        elif line.startswith('[PAUSE RESTORED]'):
            self.manual_status.setText('Held profile state verified; profile resuming')
        if line.startswith('[PAUSE READY]'):
            if self.running and not self.stopping:
                self.pause_btn.setEnabled(True)
        if line.startswith('Measurement log: '):
            self.measurement_log = Path(line.split(': ', 1)[1].strip())
            if not self.measurement_log.is_absolute():
                self.measurement_log = self.profile.parent / self.measurement_log
        if line.startswith('  Initial ch') or line.startswith('Running initial ramp'):
            self.readback_poll_enabled = True
        if line.startswith('Running initial ramp'):
            self.last_phase = 'Initial ramp'
            self.status.setText('Running — initial ramp')
            self.phase_label.setText('Phase: Initial ramp')
        elif line.startswith('Running main profile'):
            self.last_phase = 'Main profile'
            self.status.setText('Running — main profile')
            self.phase_label.setText('Phase: Main profile')
        elif line.startswith('Verifying and restoring final settings'):
            self.pause_btn.setEnabled(False)
            self.last_phase = 'Restoration'
            self.status.setText('Verifying final state / restoration')
            self.phase_label.setText('Phase: Restoration / verification')
        elif line.startswith('Running final ramp'):
            self.last_phase = 'Final ramp / cleanup'
            self.status.setText('Running — final ramp / cleanup')
            self.phase_label.setText('Phase: Final ramp / cleanup')
        elif line.startswith('Finished ') and 'time slots' in line:
            self.last_phase = 'Main profile finished'
            self.phase_label.setText('Phase: Main profile finished')
        elif line.startswith('[PAUSED]'):
            self.paused = True
            if 'phase=profile' in line:
                self.manual_connect_btn.setEnabled(True)
                self.manual_connect_btn.setText('Control paused profile')
                self.manual_resume_btn.setEnabled(True)
            self.pause_btn.setText('▶ Resume')
            self.pause_btn.setEnabled(True)
            self.status.setText('Paused — output settings held')
            self.phase_label.setText('Phase: Paused (profile time frozen)')
        elif line.startswith('[RESUMED]'):
            self.paused = False
            self.pause_manual_active = False
            self.manual_online = False
            self.manual_widgets_enabled(False)
            self.manual_disconnect_btn.setText('Disconnect (LOCAL)')
            self.manual_connect_btn.setEnabled(False)
            self.manual_connect_btn.setText('Connect to PSU')
            self.manual_resume_btn.setEnabled(False)
            self.pause_btn.setText('Ⅱ Pause')
            self.pause_btn.setEnabled(True)
            self.status.setText('Running — resumed')
            self.phase_label.setText('Phase: Resumed')
        elif line.startswith('Interrupted by Ctrl+C'):
            self.last_phase = 'Restoration after Stop'
            self.status.setText('Stopping — restoring original settings')
            self.phase_label.setText('Phase: Restoration after Stop')
        elif line.startswith('Experiment health: FAILED'):
            self.experiment_health_failed = True
            self.status.setText('Experiment health FAILED — check warnings; restoration may still be verified')
        elif line.startswith('Run status:'):
            self.run_summary = line.partition(':')[2].strip()
            self.success_summary = 'cleanup verified' in line.lower()
            self.status.setText(line.strip())
            self.phase_label.setText('Phase: Final verification')
        final = parse_final_verification(line)
        if final is not None:
            ch, good = final
            self.final_states[ch] = good
            label = self.restore_labels[ch]
            label.setText('Restoration: VERIFIED' if good else 'Restoration: NOT VERIFIED')
            label.setStyleSheet('color: #16713e; font-weight: 650;' if good else
                                'color: #b42318; font-weight: 650;')
        progress = parse_heartbeat(line)
        if progress:
            self.progress.setValue(progress['percent'])
            phase = progress['phase']
            self.last_phase = phase
            self.phase_label.setText('Phase: ' + phase.replace('_', ' ').title())
            if phase == 'paused':
                self.paused = True
                self.pause_btn.setText('▶ Resume')
                self.pause_btn.setEnabled(True)
            for ch, values in progress['readings'].items():
                self.channel_labels[ch].setText(
                    f'{values["voltage_v"]:.2f} V     {values["current_a"]:.2f} A')
            if not self.stopping and not self.paused:
                self.status.setText(f'Running — {progress["elapsed_s"]:g} s elapsed, '
                                    f'~{progress["remaining_s"]:g} s remaining')
        path = parse_report_path(line, self.output_dir or self.profile.parent)
        if path and path.is_file():
            self.report_path = path
            self.report_btn.setEnabled(True)

    def toggle_pause(self):
        if self.paused and self.pause_manual_active:
            # Resume is explicitly requested by the user; the runner restores
            # and verifies the pause-point state before advancing profile time.
            self.pause_manual_active = False
            self.manual_online = False
            self.manual_widgets_enabled(False)
            self.manual_disconnect_btn.setText('Disconnect (LOCAL)')
            self.manual_connect_btn.setEnabled(False)
        if not self.running or self.stopping or self.process is None:
            return
        pid = int(self.process.processId())
        if pid <= 0 or not hasattr(signal, 'SIGUSR1'):
            self.append_console('Pause unavailable: requires Linux SIGUSR1 and a running process.')
            return
        try:
            os.kill(pid, signal.SIGUSR1)
        except OSError as exc:
            self.append_console(f'Pause/Resume signal failed: {exc}')
            return
        # State changes are confirmed by runner [PAUSED]/[RESUMED] output.
        self.pause_btn.setEnabled(False)
        self.manual_resume_btn.setEnabled(False)
        self.append_console('GUI: Pause/Resume requested; waiting for runner acknowledgment…')

    def stop_run(self):
        if not self.running or self.stopping or not self.process:
            return
        pid = int(self.process.processId())
        if pid <= 0:
            self.append_console('Stop could not be requested; process ID unavailable.')
            return
        self.stopping = True
        self.manual_resume_btn.setEnabled(False)
        self.pause_manual_active = False
        self.manual_online = False
        self.manual_widgets_enabled(False)
        self.manual_connect_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.status.setText('Stop requested — waiting for PSU cleanup')
        self.phase_label.setText('Phase: Stop requested / restoration pending')
        self.append_console('GUI: Sending SIGINT (Ctrl+C) to runner; waiting for configured restoration and LOCAL…')
        try:
            os.kill(pid, signal.SIGINT)
        except OSError as exc:
            self.append_console(f'WARNING: Failed to send Ctrl+C: {exc}')
            self.stopping = False
            self.stop_btn.setEnabled(True)

    def process_error(self, error):
        if self.running:
            self.append_console(f'GUI: Runner process error ({error}). Check the PSU manually if cleanup was not verified.')
            if error == QProcess.FailedToStart:
                self.measurement_timer.stop()
                self.running = False
                self.pause_manual_active = False
                self.manual_online = False
                self.manual_widgets_enabled(False)
                self.cleanup_pause_control()
                self.manual_connect_btn.setEnabled(True)
                self.test_connection_btn.setEnabled(True)
                self.prepare_adapter_btn.setEnabled(bool(self.network_setup_candidates))
                self.stopping = False
                self.start_btn.setEnabled(bool(self.profile))
                self.reset_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                self.pause_btn.setEnabled(False)
                self.choose_btn.setEnabled(True)
                self.output_btn.setEnabled(True)
                self.preview_btn.setEnabled(True)
                self.status.setText('Could not start runner — check Python installation')
                self.close_console_log()
                if self.process is not None:
                    self.process.deleteLater()
                    self.process = None

    def run_finished(self, exit_code, exit_status):
        self.consume_output()
        if self.output_buffer:
            self.handle_line(self.output_buffer)
            self.output_buffer = ''
        self.poll_measurements()
        self.measurement_timer.stop()
        self.running = False
        self.pause_manual_active = False
        self.manual_online = False
        self.manual_widgets_enabled(False)
        self.manual_disconnect_btn.setText('Disconnect (LOCAL)')
        self.manual_connect_btn.setText('Connect to PSU')
        self.manual_connect_btn.setEnabled(True)
        self.test_connection_btn.setEnabled(True)
        self.prepare_adapter_btn.setEnabled(bool(self.network_setup_candidates))
        self.cleanup_pause_control()
        self.stopping = False
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.manual_resume_btn.setEnabled(False)
        self.paused = False
        self.pause_btn.setText('Ⅱ Pause')
        self.choose_btn.setEnabled(True)
        self.output_btn.setEnabled(True)
        self.override_check.setEnabled(True)
        self.set_override_enabled(self.override_check.isChecked())
        self.preview_btn.setEnabled(True)
        self.open_preview_btn.setEnabled(self.preview_path is not None)
        self.start_btn.setEnabled(self.profile is not None)
        self.reset_btn.setEnabled(True)
        kind, message = classify_run(exit_code, self.run_summary, self.final_states)
        self.status.setText(message)
        if kind == 'completed':
            if self.experiment_health_failed:
                self.status.setText('Completed / restored — EXPERIMENT HEALTH WARNING (see log)')
            self.progress.setValue(100)
            self.phase_label.setText('Phase: Complete')
        elif kind == 'stopped':
            self.phase_label.setText('Phase: Stopped — cleanup complete')
        else:
            if self.connection_not_established:
                self.status.setText('PSU connection failed — profile not started')
                self.phase_label.setText('Phase: Connection failed — no profile commands')
                QMessageBox.warning(
                    self, 'PSU connection failed',
                    'The runner could not establish a verified control connection.\n'
                    'No profile commands were issued and no PSU restoration was needed '
                    'by this attempt.\n\n'
                    'Check the Run output for the connection error. '
                    'If another application controls the PSU, disconnect it first.')
            elif exit_code == 2 and self.success_summary:
                self.status.setText('OUTPUT FAULT — cleanup verified; inspect PSU before retrying')
                self.phase_label.setText('Phase: Output fault / restored')
                QMessageBox.warning(self, 'Output fault — restoration verified',
                                    'The runner detected sustained low output and aborted the profile.\n'
                                    'The original programmed settings were verified and LOCAL was sent.\n'
                                    'Inspect the PSU and saved logs before any further testing.')
            elif 'Initial snapshot failed' in self.console.toPlainText():
                self.status.setText('Initial settings unreadable — profile not started')
                self.phase_label.setText('Phase: Initial snapshot failed — no profile commands')
                self.append_console(
                    'GUI: Original PSU settings could not be verified. Check the PSU; '
                    'Reset status clears only the GUI display.')
            else:
                self.phase_label.setText('Phase: Run error — inspect output')
            QMessageBox.warning(self, 'Run error / restoration requires attention',
                                'The runner could not confirm the required PSU state.\n'
                                'Please inspect the console and PSU settings before retrying.')
        self.append_console(f'GUI: Runner process exited with code {exit_code}.')
        self.close_console_log()
        if self.process:
            self.process.deleteLater()
        self.process = None

    def open_file(self, path):
        if not path or not Path(path).is_file():
            QMessageBox.warning(self, 'File unavailable', 'The requested file does not exist.')
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve()))):
            QMessageBox.warning(self, 'Could not open browser', str(path))

    def closeEvent(self, event):
        if self.manual_worker is not None:
            self.disconnect_manual()
            QMessageBox.information(self, 'Disconnecting manual control',
                                    'Wait until the PSU connection is closed and LOCAL has been sent.')
            event.ignore()
            return
        if self.running or (self.process and self.process.state() != QProcess.NotRunning):
            QMessageBox.information(
                self, 'Experiment still running',
                'Keep the GUI open until restoration and LOCAL have completed.\n'
                'Use Stop (safe cleanup) and wait for the runner to finish.')
            event.ignore()
            return
        if ((self.connection_probe_job and self.connection_probe_job.isRunning()) or
            (self.adapter_setup_job and self.adapter_setup_job.isRunning())):
            QMessageBox.information(self, 'Network setup in progress',
                                    'Complete the connection check or adapter setup before closing.')
            event.ignore()
            return
        if self.preview_job and self.preview_job.isRunning():
            QMessageBox.information(self, 'Preview in progress', 'Please finish the preview before closing.')
            event.ignore()
            return
        self.close_console_log()
        event.accept()


def main():
    application = QApplication(sys.argv)
    application.setApplicationName('CPX400DP Control')
    window = Window()
    window.show()
    if len(sys.argv) > 1:
        filename = Path(sys.argv[1])
        if filename.is_file():
            window.load_profile(filename)
    return application.exec() if hasattr(application, 'exec') else application.exec_()


if __name__ == '__main__':
    raise SystemExit(main())
