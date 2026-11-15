#!/usr/bin/env python3
"""CPX400DP dual-channel CSV profile runner (one TCP socket).
Usage: python3 cpx400dp_run_enhanced.py profile.csv
       python3 cpx400dp_run_enhanced.py --preview profile.csv

This is laboratory automation, not a safety interlock. Control is instrument-wide
REMOTE; a channel omitted from `channels` is not commanded, but is NOT locally
editable while remote commands are active.
"""
import argparse
import csv
import json
import os
import io
import ipaddress
import math
import re
import signal
import socket
from contextlib import ExitStack
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from cpx400dp_regulation import decode_limit_event

CONFIG_KEYS = {'host', 'channels', 'mode', 'interval_s', 'readback_interval_s', 'log_file', 'ch1_restore', 'ch2_restore', 'initial_ramp_s', 'final_ramp_s', 'progress_interval_s', 'generate_report', 'report_layout', 'abort_on_output_fault'}
NUMBER = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([VA])?\s*$')
LOG_FIELDS = ['utc_time', 'elapsed_s', 'event', 'scheduled_s', 'channel',
              'set_voltage_v', 'current_limit_a', 'requested_enable',
              'measured_voltage_v', 'measured_current_a', 'lateness_ms',
              'readback_duration_ms', 'note']


def load_profile(path, overrides=None):
    settings, content = {}, []
    with path.open(encoding='utf-8-sig', newline='') as f:
        for line_no, line in enumerate(f, 1):
            line_stripped = line.strip()
            if not content and line_stripped.startswith('#'):
                s = line_stripped[1:].strip()
                if not s or s.startswith('-'):
                    continue
                if '=' not in s:
                    # Human-readable comment in the CSV user guide.
                    continue
                k, v = [x.strip() for x in s.split('=', 1)]
                if k not in CONFIG_KEYS or k in settings:
                    raise ValueError(f'Line {line_no}: unknown or duplicate config key {k!r}')
                # Spreadsheet editors may append empty CSV cells to metadata lines.
                # Preserve meaningful commas inside values (e.g. channels=1,2).
                settings[k] = v.rstrip(',').strip()
            elif not line_stripped.strip(',').strip() or line_stripped.startswith('#'):
                continue
            else:
                content.append(line)
    has_csv_metadata = bool(settings)
    # Command-line/GUI overrides are applied in memory only. Never edit the CSV.
    allowed = {'mode', 'interval_s', 'readback_interval_s',
               'initial_ramp_s', 'final_ramp_s', 'channels'}
    if overrides:
        unknown = set(overrides) - allowed
        if unknown:
            raise ValueError('Unsupported overrides: ' + ', '.join(sorted(unknown)))
        # Channel overrides are applied only after the original CSV has been
        # fully validated, so omitted channels do not require changing columns
        # or the original restoration policy in the source file.
        settings.update({key: str(value) for key, value in overrides.items()
                         if value is not None and key != 'channels'})
    # Waveform-only CSVs do not need a metadata preamble. Legacy CSVs with
    # metadata continue to receive the same strict validation as before.
    if not has_csv_metadata:
        header = next(csv.reader(io.StringIO(''.join(content))), [])
        fields = {name.strip() for name in header}
        inferred = [ch for ch in (1, 2) if all(
            f'ch{ch}_{name}' in fields for name in
            ('voltage_v', 'current_limit_a', 'enable'))]
        if not inferred:
            raise ValueError('Waveform CSV must define at least one complete channel')
        settings = {
            'host': '169.254.51.7',  # discovery still verifies *IDN?; GUI may override
            'channels': ','.join(map(str, inferred)),
            'mode': 'linear', 'interval_s': '0.05',
            'readback_interval_s': '0.25',
            'initial_ramp_s': '0', 'final_ramp_s': '0',
            'log_file': path.stem + '_measurements.csv',
            **{f'ch{ch}_restore': 'true' for ch in inferred},
        }
        if overrides:
            settings.update({key: str(value) for key, value in overrides.items()
                             if value is not None and key != 'channels'})
    host = str(ipaddress.IPv4Address(settings['host']))
    channel_str = settings['channels'].replace(' ', '')
    if channel_str not in ('1', '2', '1,2', '2,1'):
        raise ValueError('channels must be 1, 2, or 1,2')
    channels = sorted(int(c) for c in channel_str.split(','))
    # Require an explicit final-state choice for every controlled channel.
    core = {'host', 'channels', 'mode', 'interval_s', 'readback_interval_s', 'log_file'}
    required_settings = core | {f'ch{ch}_restore' for ch in channels}
    missing = sorted(required_settings - settings.keys())
    if missing:
        raise ValueError('Missing settings: ' + ', '.join(missing))
    excluded = set((1, 2)) - set(channels)
    if any(f'ch{ch}_restore' in settings for ch in excluded):
        raise ValueError('Restore flag provided for an uncontrolled channel; remove it')
    restore_flags = {}
    for ch in channels:
        value = settings[f'ch{ch}_restore'].strip().lower()
        if value not in ('true', 'false'):
            raise ValueError(f'ch{ch}_restore must be true or false')
        restore_flags[ch] = (value == 'true')
    mode = settings['mode'].lower()
    if mode not in ('linear', 'step'):
        raise ValueError('mode must be linear or step')
    interval = float(settings['interval_s'])
    readback_interval = float(settings['readback_interval_s'])
    if not math.isfinite(interval) or not 0.05 <= interval <= 60:
        raise ValueError('interval_s must be 0.05–60 seconds (v9 provisional minimum)')
    if not math.isfinite(readback_interval) or not 0.1 <= readback_interval <= 60:
        raise ValueError('readback_interval_s must be 0.1–60 seconds')
    initial_ramp = float(settings.get('initial_ramp_s', '0'))
    final_ramp = float(settings.get('final_ramp_s', '0'))
    if not all(math.isfinite(x) and 0 <= x <= 3600 for x in (initial_ramp, final_ramp)):
        raise ValueError('initial_ramp_s and final_ramp_s must be 0–3600 seconds')
    progress_interval = float(settings.get('progress_interval_s', '10'))
    if not math.isfinite(progress_interval) or not 1 <= progress_interval <= 3600:
        raise ValueError('progress_interval_s must be 1–3600 seconds')
    log_name = settings['log_file']
    if not log_name or Path(log_name).name != log_name or log_name in ('.', '..'):
        raise ValueError('log_file must be a simple filename')
    log_path = path.parent / log_name
    if log_path.resolve() == path.resolve():
        raise ValueError('Log cannot overwrite profile')
    if not content:
        raise ValueError('Missing CSV profile table')
    # OnlyOffice and similar spreadsheet editors can export trailing empty
    # columns on header and data rows. Discard ONLY empty surplus columns.
    rows = csv.reader(io.StringIO(''.join(content)))
    raw_header = next(rows)
    while raw_header and not raw_header[-1].strip():
        raw_header.pop()
    fieldnames = [name.strip() for name in raw_header]
    required = {'time_s'}
    for ch in channels:
        required.update((f'ch{ch}_voltage_v', f'ch{ch}_current_limit_a', f'ch{ch}_enable'))
    columns = set(fieldnames)
    if not required.issubset(columns):
        raise ValueError('Missing columns: ' + ', '.join(sorted(required - columns)))
    # Explicitly forbid columns for an unmanaged channel, avoiding surprises.
    for ch in set((1,2)) - set(channels):
        if any(x.startswith(f'ch{ch}_') for x in columns):
            raise ValueError(f'Channel {ch} columns present but channel {ch} not controlled: remove these columns')
    if len(fieldnames) != len(columns):
        raise ValueError('Duplicate CSV column')
    if columns != required:
        raise ValueError('Unexpected CSV columns: ' + ', '.join(sorted(columns - required)))
    parsed_rows = []
    for line_no, cells in enumerate(rows, 2):
        if not cells or all(not cell.strip() for cell in cells):
            continue
        if len(cells) > len(fieldnames):
            if any(cell.strip() for cell in cells[len(fieldnames):]):
                raise ValueError(f'CSV data row {line_no} has extra nonempty values')
            cells = cells[:len(fieldnames)]
        # A trailing empty enable cell may have been elided by the editor.
        if len(cells) < len(fieldnames):
            omitted = fieldnames[len(cells):]
            if not all(name.endswith('_enable') for name in omitted):
                raise ValueError(f'CSV data row {line_no} is missing required values')
            cells += [''] * len(omitted)
        parsed_rows.append((line_no, dict(zip(fieldnames, cells))))
    pts = []
    for idx, row in parsed_rows:
        try:
            t = float(row['time_s'])
            values = {}
            for ch in channels:
                v = float(row[f'ch{ch}_voltage_v'])
                a = float(row[f'ch{ch}_current_limit_a'])
                en_s = row[f'ch{ch}_enable'].strip()
                if en_s.lower() not in ('0', '1', 'hold', 'keep', ''):
                    raise ValueError('Enable must be 0, 1, hold, or blank')
                if not all(math.isfinite(x) for x in (v,a)) or not (0 <= v <= 60 and 0 <= a <= 20):
                    raise ValueError('Setpoint outside 0–60 V / 0–20 A')
                values[ch] = (v, a, int(en_s) if en_s in ('0', '1') else None)
        except (ValueError, TypeError) as exc:
            raise ValueError(f'Invalid CSV data row {idx}: {exc}') from exc
        if not math.isfinite(t) or t < 0 or (pts and t <= pts[-1][0]):
            raise ValueError(f'Invalid/nonincreasing timestamp at CSV row {idx}')
        pts.append((t, values))
    if not pts or pts[0][0] != 0:
        raise ValueError('First profile timestamp must be 0')
    if overrides and overrides.get('channels') is not None:
        requested = str(overrides['channels']).replace(' ', '')
        if requested not in ('1', '2', '1,2', '2,1'):
            raise ValueError('Channel override must select CH1, CH2, or both (at least one)')
        selected = sorted({int(c) for c in requested.split(',')})
        if not set(selected).issubset(channels):
            raise ValueError('Cannot enable a channel missing from the original CSV profile')
        channels = selected
        restore_flags = {ch: restore_flags[ch] for ch in channels}
        pts = [(time_s, {ch: values[ch] for ch in channels}) for time_s, values in pts]
    return host, channels, mode, interval, readback_interval, log_path, pts, restore_flags, initial_ramp, final_ramp, progress_interval


def at_time(points, t, mode):
    lo, hi = 0, len(points) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if points[mid][0] <= t + 1e-9:
            lo = mid
        else:
            hi = mid - 1
    j = lo
    vals = {}
    for ch, (v, a, enable) in points[j][1].items():
        if mode == 'linear' and j + 1 < len(points):
            t0, t1 = points[j][0], points[j+1][0]
            frac = max(0.0, min(1.0, (t-t0)/(t1-t0)))
            v1, a1, _ = points[j+1][1][ch]
            v += (v1-v)*frac
            a += (a1-a)*frac
        vals[ch] = (v, a, enable)
    return vals


def send(sock, cmd):
    sock.sendall((cmd + '\n').encode('ascii'))


def read_line(sock, pending):
    while b'\n' not in pending:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError('PSU closed connection')
        pending += chunk
        if len(pending) > 8192:
            raise ValueError('Oversize PSU response')
    first, pending = pending.split(b'\n', 1)
    return first.decode('ascii', 'replace').strip(), pending


def measure(sock, ch, pending):
    res = []
    for prefix, unit in ((f'V{ch}O?', 'V'), (f'I{ch}O?', 'A')):
        send(sock, prefix)
        reply, pending = read_line(sock, pending)
        m = NUMBER.fullmatch(reply)
        if m is None or (m.group(2) and m.group(2) != unit):
            raise ValueError(f'Invalid {prefix} response {reply!r}')
        res.append(float(m.group(1)))
    return res, pending


def query_expected(sock, command, pending, matches, *, max_unexpected=4):
    """Send one query and read until its correctly typed reply arrives.

    A stale unlabelled OP response must not be mistaken for a V/I setting.
    Never guess at an OP reply from a tagged V/I reply; reject unmatched data
    after a small bounded number of lines. All of this is read-only.
    """
    send(sock, command)
    unexpected = []
    for _ in range(max_unexpected + 1):
        try:
            reply, pending = read_line(sock, pending)
        except (OSError, ValueError, ConnectionError) as exc:
            raise ValueError(f'{command}: no matching response; '
                             f'unexpected lines={unexpected!r}; '
                             f'{type(exc).__name__}: {exc}') from exc
        if matches(reply):
            if unexpected:
                print(f'[SNAPSHOT SYNC] {command}: discarded unexpected prior '
                      f'replies {unexpected!r}; accepted {reply!r}', flush=True)
            return reply, pending
        unexpected.append(reply)
    raise ValueError(f'{command}: no matching response after '
                     f'{max_unexpected + 1} replies: {unexpected!r}')


def snapshot(sock, channels, pending):
    """Read programmed settings using response type, not response position.

    Unlike output-meter readings, V?/I? replies are tagged.  OP? replies
    are untagged 0/1; by matching V and I *before* sending OP? we avoid
    consuming an OP reply as a voltage or current value.
    """
    state = {}
    for ch in channels:
        vm_re = re.compile(rf'V\s*{ch}\s+([+-]?(?:\d+(?:\.\d*)?|\.\d+))', re.I)
        im_re = re.compile(rf'I\s*{ch}\s+([+-]?(?:\d+(?:\.\d*)?|\.\d+))', re.I)
        v_response, pending = query_expected(
            sock, f'V{ch}?', pending, lambda line: vm_re.fullmatch(line) is not None)
        i_response, pending = query_expected(
            sock, f'I{ch}?', pending, lambda line: im_re.fullmatch(line) is not None)
        op_response, pending = query_expected(
            sock, f'OP{ch}?', pending, lambda line: line in ('0', '1'))
        state[ch] = (float(vm_re.fullmatch(v_response).group(1)),
                     float(im_re.fullmatch(i_response).group(1)), int(op_response))
    return state, pending


def verify_initial_snapshot(sock, channels, pending):
    """Require two complete matching read-only snapshots before any setpoints."""
    first, pending = snapshot(sock, channels, pending)
    second, pending = snapshot(sock, channels, pending)
    for ch in channels:
        a, b = first[ch], second[ch]
        if abs(a[0] - b[0]) > 0.011 or abs(a[1] - b[1]) > 0.011 or a[2] != b[2]:
            raise ValueError(f'Initial state inconsistent on channel {ch}: '
                             f'first={a!r}, second={b!r}; no output commands sent')
    print('[SNAPSHOT VERIFIED] Two matching programmed-state reads for '
          + ', '.join(f'ch{ch}' for ch in channels), flush=True)
    return second, pending

class OutputHealthMonitor:
    """Advisory stuck-low monitor; never alters instrument state.

    Counts samples only when a channel is commanded ON and >= 2 V.
    It deliberately ignores normal tracking errors and settling transients.
    Three consecutive low-voltage samples spanning >=0.5 s trigger once,
    with rearming after the output recovers. Readbacks are not added.
    """
    def __init__(self):
        self.bad = {}
        self.reported = set()
        self.warnings = 0

    def update(self, ch, expected_v, enabled, measured_v, phase, when):
        if phase not in ('profile', 'paused') or enabled != 1 or expected_v < 2.0:
            self.bad.pop(ch, None)
            return None
        low = measured_v < max(0.25, 0.15 * expected_v)
        if not low:
            self.bad.pop(ch, None)
            self.reported.discard(ch)
            return None
        count, first = self.bad.get(ch, (0, when))
        count += 1
        self.bad[ch] = (count, first)
        if ch not in self.reported and count >= 3 and when - first >= 0.45:
            self.reported.add(ch)
            self.warnings += 1
            return (f'CH{ch}: commanded ON at {expected_v:.3f} V, '
                    f'but measured {measured_v:.3f} V for {when-first:.2f}s; '
                    'check PSU indicators/output (advisory, no automatic action)')
        return None


class OutputFaultAbort(RuntimeError):
    """Sustained physical output collapse; run cleanup in finally."""


def profile_option(path, key, default):
    with Path(path).open(encoding='utf-8-sig') as source:
        for line in source:
            if not line.lstrip().startswith('#'):
                break
            item = line.lstrip()[1:].strip().rstrip(',').strip()
            if '=' in item:
                k, v = [part.strip() for part in item.split('=', 1)]
                if k == key:
                    if v.lower() not in ('true', 'false'):
                        raise ValueError(f'{key} must be true or false')
                    return v
    return default


class CommandOptimizer:
    """Suppress unchanged V/I commands, comparing formatted instrument values.

    Only committed transmissions update the cache; restoration bypasses this
    cache and is always sent explicitly. Enable commands are not suppressed here.
    """
    def __init__(self):
        self.sent = {}
        self.groups = 0
        self.instructions = 0
        self.suppressed = 0
        self.total_send_ms = 0.0
        self.max_send_ms = 0.0

    def settings(self, vals):
        commands = []
        updates = {}
        for ch, (v, a) in vals.items():
            for code, value in ((f'V{ch}', v), (f'I{ch}', a)):
                rounded = f'{value:.3f}'
                if self.sent.get(code) == rounded:
                    self.suppressed += 1
                else:
                    commands.append(f'{code} {rounded}')
                    updates[code] = rounded
        return commands, updates

    def transmit(self, sock, commands, updates=None, *, enable_codes=()):
        if not commands:
            return
        begin = time.monotonic()
        send(sock, ';'.join(commands))
        duration_ms = (time.monotonic() - begin) * 1000
        self.groups += 1
        self.instructions += len(commands)
        self.total_send_ms += duration_ms
        self.max_send_ms = max(self.max_send_ms, duration_ms)
        if updates:
            self.sent.update(updates)


def finish_channels(sock, channels, saved, restore_flags, pending, log):
    """Apply final settings, allowing the instrument time to process them.

    A single immediate query is not sufficient: the PSU may report its previous
    programmed voltage briefly after receiving the restore command.
    """
    errors = []
    targets = {}

    def apply_final(ch):
        voltage, limit, enabled = targets[ch]
        if enabled == 0:
            send(sock, f'OP{ch} 0')
        send(sock, f'V{ch} {voltage:.3f};I{ch} {limit:.3f}')
        if enabled == 1 and restore_flags[ch]:
            # This does not turn an originally ON output OFF first.
            send(sock, f'OP{ch} 1')

    for ch in channels:
        targets[ch] = saved[ch] if restore_flags[ch] else (0.0, 0.0, 0)
        try:
            apply_final(ch)
            voltage, limit, enabled = targets[ch]
            log('final_state_sent', channel=ch, set_voltage_v=f'{voltage:.3f}',
                current_limit_a=f'{limit:.3f}', requested_enable=enabled,
                note='Restore original state' if restore_flags[ch] else 'OFF, 0 V, 0 A')
        except Exception as exc:
            errors.append(f'ch{ch}: final command failed: {exc}')
            log('final_state_error', channel=ch, note=str(exc))

    for ch in channels:
        expected = targets[ch]
        deadline = time.monotonic() + 2.0
        resent = False
        attempts = 0
        last_error = None
        while True:
            attempts += 1
            try:
                actual, pending = snapshot(sock, [ch], pending)
                av, ai, ae = actual[ch]
                ev, ei, ee = expected
                if abs(av-ev) <= 0.011 and abs(ai-ei) <= 0.011 and ae == ee:
                    log('final_state_verified', channel=ch,
                        set_voltage_v=f'{av:.3f}', current_limit_a=f'{ai:.3f}',
                        requested_enable=ae,
                        note=f'Confirmed after {attempts} query attempt(s)')
                    break
                last_error = f'expected {expected!r}, actual {(av, ai, ae)!r}'
            except Exception as exc:
                last_error = str(exc)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                msg = f'ch{ch}: verification failed after {attempts} tries: {last_error}'
                errors.append(msg)
                log('final_state_error', channel=ch, note=msg)
                break
            if not resent and remaining < 1.35:
                # Retry the command once in case a command was missed.
                try:
                    apply_final(ch)
                    log('final_state_resent', channel=ch, note='Retry after delayed verification')
                except Exception as exc:
                    log('final_state_error', channel=ch, note=f'Resend failed: {exc}')
                resent = True
            time.sleep(min(0.10, max(0, remaining)))
    if errors:
        print('WARNING: final-state errors: ' + '; '.join(errors), file=sys.stderr)
    return errors


def verify_physical_outputs(sock, channels, saved, restore_flags, pending, log):
    """Post-restore *advisory* readback before LOCAL; never changes setpoints.

    Only meaningful for restored, enabled, nonzero-voltage channels. An OFF
    output or a zero-voltage target is N/A, not a failed physical check.
    A PSU regulation state cannot be conclusively inferred from this voltage
    readback alone (e.g. current limiting or external loading).
    """
    results = {}
    for ch in channels:
        if not restore_flags[ch]:
            results[ch] = 'NOT CHECKED (configured OFF)'
            continue
        voltage, limit, enabled = saved[ch]
        if not enabled or voltage < 1.0 or limit <= 0:
            results[ch] = ('N/A (output OFF)' if not enabled else 'N/A (output ON, near-zero set voltage)' if voltage < 1.0 else 'N/A (current limit <= 0)')
            log('physical_output_skipped', channel=ch, set_voltage_v=f'{voltage:.3f}',
                requested_enable=enabled, note=results[ch])
            continue
        # Wait briefly for final ramp voltage to settle. This is independent of
        # scheduled readbacks, and happens only AFTER programmed verification.
        deadline = time.monotonic() + 1.6
        mv = None
        last_error = None
        while True:
            try:
                (mv, _), pending = measure(sock, ch, pending)
                if abs(mv-voltage) <= max(0.5, 0.05 * voltage):
                    results[ch] = 'MATCHED (sampled, not continuous proof)'
                    log('physical_output_checked', channel=ch,
                        set_voltage_v=f'{voltage:.3f}', measured_voltage_v=f'{mv:.4f}',
                        requested_enable=enabled, note='MATCHED; 0.5 V or 5% tolerance')
                    break
            except Exception as exc:
                last_error = str(exc)
            if time.monotonic() >= deadline:
                results[ch] = 'WARNING (not confirmed)'
                log('physical_output_warning', channel=ch,
                    set_voltage_v=f'{voltage:.3f}',
                    measured_voltage_v=f'{mv:.4f}' if mv is not None else '',
                    requested_enable=enabled,
                    note=f'No matching post-restore voltage: {last_error or "settling/mismatch"}')
                print(f'[OUTPUT HEALTH WARNING] CH{ch} restored setpoint {voltage:.3f} V '
                      f'but physical readback not confirmed (latest {mv}); '
                      'no automatic action', flush=True)
                break
            time.sleep(0.15)
    return results, pending


def ramp_values(a, b, fraction):
    return (a[0] + (b[0]-a[0])*fraction, a[1] + (b[1]-a[1])*fraction)


def schedule_for(duration, interval, extra=()):
    """Yield ticks in time order without materialising the regular time grid.

    A 1000-hour run at 50 ms has 72 million regular ticks; only the CSV
    keyframes need to be held in memory. Preserve 9-decimal tick rounding
    and de-duplication from the legacy scheduler.
    """
    keyframes = sorted(set(round(t, 9) for t in extra) | {round(duration, 9)})
    n_regular = math.ceil(duration / interval)
    regular_i = 0
    extra_i = 0
    previous = None
    while regular_i < n_regular or extra_i < len(keyframes):
        regular = round(regular_i * interval, 9) if regular_i < n_regular else math.inf
        if regular >= round(duration, 9):
            regular = math.inf
            regular_i = n_regular
        keyframe = keyframes[extra_i] if extra_i < len(keyframes) else math.inf
        tick = min(regular, keyframe)
        if regular == tick:
            regular_i += 1
        if keyframe == tick:
            extra_i += 1
        if tick != previous:
            yield tick
            previous = tick




def classify_high_readback(measured, commanded, sent_history, now, readback_interval):
    """Classify high voltage samples using the recent programmed voltage envelope.

    Returns 'normal', 'settling', or 'unexplained'. A recently commanded
    higher voltage can explain a lagging down-step; it cannot excuse voltage
    far above anything recently commanded. Advisory only, not an interlock.
    """
    if commanded < 1.0 or measured <= commanded + max(1.0, 0.20*commanded):
        return 'normal'
    window = max(0.75, 3.0*readback_interval)
    recent = [voltage for sent_at, voltage in sent_history
              if 0 <= now-sent_at <= window]
    ceiling = max([commanded] + recent)
    if ceiling > commanded + 0.1 and measured <= ceiling + max(0.5, 0.08*ceiling):
        return 'settling'
    return 'unexplained'

MIN_SETPOINT_GAP_S = 0.050


def validate_schedule(points, interval, initial_ramp, final_ramp, restoring):
    """Check minimum tick spacing in O(number of CSV keyframes), not O(ticks).

    Regular ticks are interval apart by construction. Only ticks adjacent
    to an irregular keyframe or phase endpoint can create shorter gaps.
    Phases are checked independently; no PSU connection is opened.
    """
    phases = [('main profile', points[-1][0], [t for t, _ in points])]
    if initial_ramp > 0:
        phases.append(('initial ramp', initial_ramp, []))
    if final_ramp > 0 and restoring:
        phases.append(('final ramp', final_ramp, []))
    min_found = None
    for label, duration, keyframes in phases:
        count = math.ceil(duration / interval)
        # Inspect 0, the final regular ticks, and neighbouring regular
        # ticks for every user keyframe / phase boundary. This is exact
        # under the same 9-decimal rounding used by schedule_for().
        candidates = {0.0, round(duration, 9)}
        for t in [*keyframes, duration]:
            index = max(0, min(count - 1, math.floor(t / interval)))
            for i in (index - 1, index, index + 1):
                if 0 <= i < count:
                    tick = round(i * interval, 9)
                    if tick < round(duration, 9):
                        candidates.add(tick)
            candidates.add(round(t, 9))
        if count >= 2:
            # A regular interior pair is interval apart, even when no
            # nearby CSV keyframe exists (and no endpoints are close).
            min_found = interval if min_found is None else min(min_found, interval)
        ticks = sorted(candidates)
        for left, right in zip(ticks, ticks[1:]):
            gap = right - left
            min_found = gap if min_found is None else min(min_found, gap)
            if gap < MIN_SETPOINT_GAP_S - 1e-8:
                raise ValueError(
                    f'Unsafe scheduled setpoint spacing in {label}: '
                    f'{left:.6f}s → {right:.6f}s = {gap*1000:.3f} ms '
                    f'(< 50 ms). CSV keyframe(s) in this interval: '
                    + (', '.join(f'{t:g}s' for t in keyframes if left-1e-8 <= t <= right+1e-8)
                       or 'none (regular/end-of-phase tick)').replace('<', 'less than'))
    return min_found if min_found is not None else interval


def effective_heartbeat(estimated_duration, user_limit):
    """Never slower than 10 seconds or 10% of estimated unpaused duration."""
    return min(10., user_limit, max(0.1, estimated_duration / 10.))


DIAGNOSTIC_QUERIES = ('*STB?', 'LSR1?', 'LSR2?', '*ESR?', 'EER?', 'QER?')


def collect_diagnostics(sock, pending, label, log):
    """Best-effort raw status snapshot. Some status reads clear event registers.

    Preserve raw answers; avoid decoding uncertain firmware-specific bits.
    Failed/timeout queries are logged, but never prevent a LOCAL attempt.
    """
    results = {}
    for command in DIAGNOSTIC_QUERIES:
        try:
            # A numeric response can be 0x-prefixed or plain decimal.
            response, pending = query_expected(
                sock, command, pending,
                lambda value: re.fullmatch(r'(?:0[xX][0-9a-fA-F]+|[0-9]+)', value.strip()) is not None,
                max_unexpected=2)
            results[command] = response
            log('diagnostic', note=f'{label}: {command} = {response} (raw; event registers may clear on read)')
            print(f'[PSU DIAGNOSTIC] {label}: {command} = {response}', flush=True)
        except Exception as exc:
            results[command] = f'ERROR: {type(exc).__name__}: {exc}'
            log('diagnostic_error', note=f'{label}: {command}: {results[command]}')
            print(f'[PSU DIAGNOSTIC WARNING] {label}: {command}: {exc}', flush=True)
            # Lost replies after timeout can desynchronise subsequent queries.
            # A read error is not treated as clean status; continue only when
            # replies can be matched by their type. The snapshots are advisory.
    return pending, results


def execute(path, output_dir=None, overrides=None, run_id=None, *, psu_ip=None, psu_interface=None, no_discovery=False, pause_control_socket=None):
    (host, channels, mode, interval, rb_interval, log_path, pts,
     restore_flags, initial_ramp, final_ramp, progress_interval) = load_profile(path, overrides=overrides)
    if psu_ip is not None:
        host = str(ipaddress.IPv4Address(psu_ip))
    if output_dir is not None:
        output_dir = Path(output_dir).expanduser().resolve()
        if not output_dir.is_dir():
            raise ValueError(f'Output directory does not exist: {output_dir}')
        log_path = output_dir / log_path.name
    if run_id:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
            raise ValueError('run_id must contain only letters, numbers, underscore or hyphen')
        log_path = log_path.with_name(f'{log_path.stem}_{run_id}{log_path.suffix}')
    if log_path.resolve() == path.resolve():
        raise ValueError('Measurement log must not overwrite the input profile')
    duration = pts[-1][0]
    # Lazy schedule; recreate its iterator only at execution, never before I/O.
    smallest_gap = validate_schedule(pts, interval, initial_ramp, final_ramp,
                                     any(restore_flags.values()))
    print(f'Host {host}:9221; channels {channels}; {mode}; {interval:g}s steps; '
          f'{rb_interval:g}s readbacks; duration {duration:g}s')
    print(f'Initial ramp: {initial_ramp:g}s; final ramp: {final_ramp:g}s')
    print('End/error: ' + ', '.join(f'ch{ch}: '+ ('restore saved state' if restore_flags[ch] else 'OFF / 0 V / 0 A') for ch in channels))
    estimated_total = initial_ramp + duration + (final_ramp if any(restore_flags.values()) else 0)
    progress_interval = effective_heartbeat(estimated_total, progress_interval)
    print(f'Progress heartbeat: every {progress_interval:g}s (wall clock); estimated profile duration {estimated_total:g}s')
    print(f'Smallest scheduled within-phase gap: {smallest_gap*1000:.3f} ms (not a guarantee of actual hardware-command spacing)')
    print(f'Measurement log: {log_path}')
    if overrides:
        print('GUI/CLI overrides (CSV unchanged): ' + ', '.join(
            f'{k}={v}' for k, v in sorted(overrides.items())))
    with log_path.open('x' if run_id else 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()
        start = None
        # Summary counters are updated from the same events as the CSV log.
        stats = {'readbacks_ok': 0, 'readbacks_failed': 0,
                 'max_lateness_ms': 0.0, 'status': 'ERROR',
                 'final': {ch: 'NOT VERIFIED' for ch in channels},
                 'local': 'NOT SENT', 'physical': {ch: 'NOT CHECKED' for ch in channels}}
        next_readback_at = None
        next_progress_at = None
        output_health = OutputHealthMonitor()
        optimizer = CommandOptimizer()
        abort_fault = (profile_option(path, 'abort_on_output_fault', 'true').lower() == 'true')
        fault_abort = False
        implausible_count = 0
        transient_count = 0
        recent_setpoints = {}  # (monotonic time, programmed voltage) per channel; includes pre-downstep value
        prior_commanded_voltage = {}  # last voltage actually commanded per channel
        latest_readings = {}  # Populated by existing readbacks; no extra PSU queries.
        # The last V/I/enable sent is the stationary target during Pause.
        last_setpoints = {}
        last_enables = {}
        manual_pause_dirty = False
        pause_manual_targets = {}
        pause_original = {}
        pause_listener = None
        last_pause_write_at = None
        last_pause_state_emit_at = None
        last_pause_lsr_poll_at = None
        pause_limit_modes = {ch: None for ch in channels}
        # Kubuntu/POSIX: SIGUSR1 toggles pause and resume. The handler only
        # changes an in-memory flag; it never talks to the instrument.
        pause_wanted = False
        pause_started = None
        paused_total = 0.0
        active_phase = 'initial_ramp'
        previous_usr1 = None
        if hasattr(signal, 'SIGUSR1'):
            previous_usr1 = signal.getsignal(signal.SIGUSR1)
            def request_pause_toggle(signum, frame):
                nonlocal pause_wanted
                pause_wanted = not pause_wanted
            signal.signal(signal.SIGUSR1, request_pause_toggle)
            print('[PAUSE READY] SIGUSR1 handler installed', flush=True)

        def active_elapsed(now=None):
            now = time.monotonic() if now is None else now
            # Elapsed experiment time excludes all pauses, including current one.
            return max(0.0, now - start - paused_total -
                       (now - pause_started if pause_started is not None else 0.0))

        def poll_paused_regulation(sock, pending):
            # LSR<N>? is a read-and-clear EVENT register, so preserve only
            # the last unambiguous observed mode and label it as historical.
            for ch in channels:
                try:
                    answer, pending = query_expected(
                        sock, f'LSR{ch}?', pending,
                        lambda line: re.fullmatch(r'(?:0[xX][0-9a-fA-F]+|[0-9]+)', line.strip()) is not None)
                    pause_limit_modes[ch] = decode_limit_event(
                        answer, bool(pause_manual_targets[ch][2]), pause_limit_modes[ch])
                    # Since LSR is read-and-clear, preserve nonzero raw
                    # event bits in the measurement log for later diagnostics.
                    if int(answer, 0) if answer.strip().lower().startswith('0x') else int(answer):
                        log('limit_event_sample', channel=ch,
                            note=f'paused LSR{ch}?={answer}; read-and-clear')
                except (OSError, ValueError, ConnectionError) as exc:
                    pause_limit_modes[ch] = None
                    log('limit_event_error', channel=ch,
                        note=f'paused LSR{ch}? unavailable: {exc}')
            return pending

        def emit_pause_manual_state(sock, pending):
            # Programmed settings, not assumed command values, are shown to user.
            states, pending = snapshot(sock, channels, pending)
            readings = {}
            for ch in channels:
                readings[ch], pending = measure(sock, ch, pending)
            pending = poll_paused_regulation(sock, pending)
            payload = {str(ch): {'programmed': list(states[ch]), 'measured': readings[ch],
                                  'regulation': pause_limit_modes[ch]}
                       for ch in channels}
            print('[PAUSE MANUAL STATE] ' + json.dumps(payload, separators=(',', ':')), flush=True)
            return pending

        def drain_pause_requests():
            if pause_listener is None:
                return
            while True:
                try:
                    pause_listener.recv(2048)
                except BlockingIOError:
                    break

        def pause_send(sock, commands):
            nonlocal last_pause_write_at
            if last_pause_write_at is not None:
                remaining = MIN_SETPOINT_GAP_S - (time.monotonic() - last_pause_write_at)
                if remaining > 0:
                    time.sleep(remaining)
            send(sock, commands)
            last_pause_write_at = time.monotonic()

        def process_pause_requests(sock, pending):
            nonlocal manual_pause_dirty
            if pause_listener is None:
                return pending
            for _ in range(12):  # bounded per checkpoint, preserve readback cadence
                try:
                    raw = pause_listener.recv(2048)
                except BlockingIOError:
                    break
                try:
                    request = json.loads(raw.decode('utf-8'))
                    action = request['action']
                    ch = request['channel']
                    val = request['value']
                    if type(ch) is not int or ch not in channels:
                        raise ValueError('Channel not controlled by this profile')
                    if action not in ('voltage', 'current', 'output'):
                        raise ValueError('Invalid manual action')
                    if action == 'output':
                        if type(val) is not int or val not in (0, 1):
                            raise ValueError('Output must be 0 or 1')
                        cmd = f'OP{ch} {val}'
                    else:
                        if type(val) not in (float, int) or not math.isfinite(val):
                            raise ValueError('Setpoint must be finite')
                        if not 0 <= val <= (60 if action == 'voltage' else 20):
                            raise ValueError('Setpoint outside PSU range')
                        cmd = f'{"V" if action == "voltage" else "I"}{ch} {val:.3f}'
                    pause_send(sock, cmd)
                    manual_pause_dirty = True
                    # Invalidate optimizer's setpoint cache. This forces the profile
                    # to reassert its own values on subsequent scheduled slots.
                    optimizer.sent.clear()
                    # Read back programmed state before reporting command verified.
                    deadline = time.monotonic() + 1.7
                    actual = None
                    index = {'voltage':0, 'current':1, 'output':2}[action]
                    while time.monotonic() < deadline:
                        states, pending = snapshot(sock, [ch], pending)
                        actual = states[ch]
                        if abs(actual[index] - val) <= (0 if index == 2 else .011):
                            break
                        time.sleep(.075)
                    else:
                        raise ValueError(f'CH{ch} {action}: programmed readback did not verify (last={actual})')
                    pause_manual_targets[ch] = tuple(actual)
                    ev = 'manual_setpoint'
                    log(ev, f'{active_elapsed():.6f}', ch,
                        set_voltage_v=f'{actual[0]:.3f}', current_limit_a=f'{actual[1]:.3f}',
                        requested_enable=actual[2], note=f'PAUSED manual {cmd}; readback verified')
                    if action == 'output':
                        log('output_transition', f'{active_elapsed():.6f}', ch,
                            requested_enable=actual[2], note='Manual change during pause')
                    display_value = str(val) if action == 'output' else f'{float(val):.3f}'
                    print(f'[PAUSE MANUAL OK] CH{ch} {action}={display_value}; verified', flush=True)
                    pending = emit_pause_manual_state(sock, pending)
                except Exception as exc:
                    print('[PAUSE MANUAL ERROR] ' + str(exc), flush=True)
                    log('manual_error', note=str(exc))
            return pending

        def restore_pause_point(sock, pending):
            nonlocal manual_pause_dirty
            if not manual_pause_dirty:
                return pending
            print('[PAUSE RESTORE] Returning to programmed pause-point state before resuming profile', flush=True)
            # Do not alter the pre-run snapshot used by final/error restoration.
            for ch, (v, a, enabled) in pause_original.items():
                # When the pause-point target is OFF, disable before changing
                # voltage/current to avoid a powered intermediate state.
                if not enabled:
                    pause_send(sock, f'OP{ch} 0;V{ch} {v:.3f};I{ch} {a:.3f}')
                else:
                    pause_send(sock, f'V{ch} {v:.3f};I{ch} {a:.3f};OP{ch} 1')
            for ch, expected in pause_original.items():
                deadline = time.monotonic() + 2.0
                actual = None
                while time.monotonic() < deadline:
                    states, pending = snapshot(sock, [ch], pending)
                    actual = states[ch]
                    if (abs(actual[0] - expected[0]) <= .011 and
                        abs(actual[1] - expected[1]) <= .011 and
                        actual[2] == expected[2]):
                        break
                    time.sleep(.08)
                else:
                    raise RuntimeError(f'Cannot resume safely: CH{ch} pause-state restore failed; '
                                       f'wanted {expected}, read {actual}')
                log('pause_hold', f'{active_elapsed():.6f}', ch,
                    set_voltage_v=f'{expected[0]:.3f}', current_limit_a=f'{expected[1]:.3f}',
                    requested_enable=expected[2], note='Verified return from manual to profile pause state')
                log('output_transition', f'{active_elapsed():.6f}', ch,
                    requested_enable=expected[2], note='Return to profile after manual pause')
            # Leave at least the validated minimum group spacing before the
            # runner can issue the next ordinary scheduled profile change.
            if last_pause_write_at is not None:
                remaining = MIN_SETPOINT_GAP_S - (time.monotonic() - last_pause_write_at)
                if remaining > 0:
                    time.sleep(remaining)
            manual_pause_dirty = False
            optimizer.sent.clear()
            print('[PAUSE RESTORED] All selected channels verified; resuming profile', flush=True)
            return pending

        def pause_checkpoint(phase):
            nonlocal pause_started, paused_total, next_readback_at, active_phase, pending
            nonlocal pause_original, pause_manual_targets, manual_pause_dirty, last_pause_state_emit_at, last_pause_lsr_poll_at
            active_phase = phase
            if pause_wanted and pause_started is None:
                pause_started = time.monotonic()
                manual_pause_dirty = False
                last_pause_state_emit_at = None
                last_pause_lsr_poll_at = None
                pause_limit_modes.update({ch: None for ch in channels})
                drain_pause_requests()  # never execute old requests from a prior pause
                # The runner is still the only PSU connection owner.
                # Capture the intended profile state, not potentially stale
                # immediately-after-command programmed readbacks.
                pause_original = {ch:(last_setpoints[ch][0],last_setpoints[ch][1],last_enables[ch])
                                  for ch in channels}
                pause_manual_targets = dict(pause_original)
                log('pause', note=f'phase={phase}; holding last commanded setpoints')
                for ch, (v, a) in last_setpoints.items():
                    log('pause_hold', f'{active_elapsed():.6f}', ch,
                        set_voltage_v=f'{v:.3f}', current_limit_a=f'{a:.3f}',
                        requested_enable=last_enables.get(ch, 'hold'))
                print(f'[PAUSED] phase={phase}; holding latest PSU settings; '
                      'press Resume or Stop', flush=True)
                if phase == 'profile' and pause_listener is not None:
                    print('[PAUSE MANUAL READY] Use the Manual Control tab; profile time is frozen', flush=True)
                    pending = emit_pause_manual_state(sock, pending)
                heartbeat('paused', force=True)
            while pause_wanted:
                if phase == 'profile':
                    pending = process_pause_requests(sock, pending)
                if last_setpoints:
                    targets = ({ch: pause_manual_targets[ch][:2] for ch in channels}
                               if manual_pause_dirty else last_setpoints)
                    enables = ({ch: pause_manual_targets[ch][2] for ch in channels}
                               if manual_pause_dirty else last_enables)
                    pending = readbacks(sock, list(last_setpoints), pending,
                                        'manual_pause' if manual_pause_dirty else 'paused',
                                        active_elapsed(), targets, enables)
                # Reuse the runner's existing measurement samples for the
                # paused Manual tab; don't add another polling connection.
                now = time.monotonic()
                if phase == 'profile' and (last_pause_lsr_poll_at is None or
                                          now-last_pause_lsr_poll_at >= 1.0):
                    pending = poll_paused_regulation(sock, pending)
                    last_pause_lsr_poll_at = now
                if (phase == 'profile' and
                    (last_pause_state_emit_at is None or now-last_pause_state_emit_at >= .25) and
                    all(ch in latest_readings for ch in channels)):
                    payload = {str(ch): {
                        'programmed': list(pause_manual_targets[ch]),
                        'measured': list(latest_readings[ch]),
                        'regulation': pause_limit_modes[ch]} for ch in channels}
                    print('[PAUSE MANUAL STATE] ' + json.dumps(payload, separators=(',', ':')), flush=True)
                    last_pause_state_emit_at = now
                heartbeat('paused')
                time.sleep(min(.025, max(.005,
                    (next_readback_at or time.monotonic()) - time.monotonic())))
            if pause_started is not None:
                drain_pause_requests()  # reject commands racing with Resume
                pending = restore_pause_point(sock, pending)
                duration = time.monotonic() - pause_started
                paused_total += duration
                pause_started = None
                for ch, (v, a) in last_setpoints.items():
                    log('pause_hold', f'{active_elapsed():.6f}', ch,
                        set_voltage_v=f'{v:.3f}', current_limit_a=f'{a:.3f}',
                        requested_enable=last_enables.get(ch, 'hold'))
                log('resume', note=f'phase={phase}; paused {duration:.3f} s')
                print(f'[RESUMED] phase={phase}; pause duration {duration:.3f}s', flush=True)
                heartbeat(phase, force=True)
        def heartbeat(phase, force=False):
            nonlocal next_progress_at
            if start is None or next_progress_at is None:
                return
            now = time.monotonic()
            if force or now + 1e-6 >= next_progress_at:
                elapsed = active_elapsed(now)
                remaining = max(0.0, estimated_total - elapsed)
                readings = ' | '.join(
                    f'ch{ch}: {latest_readings[ch][0]:.3f} V, {latest_readings[ch][1]:.3f} A'
                    if ch in latest_readings else f'ch{ch}: awaiting readback'
                    for ch in channels)
                print(f'[PROGRESS] {elapsed:.1f}/{estimated_total:.1f}s '
                      f'(~{remaining:.1f}s remaining) | {phase} | {readings} | '
                      f'readbacks {stats["readbacks_ok"]} OK/{stats["readbacks_failed"]} failed | '
                      f'max lateness {stats["max_lateness_ms"]:.3f} ms', flush=True)
                # Advance by an integer number of periods, no accumulated drift.
                if now + 1e-6 >= next_progress_at:
                    next_progress_at += (math.floor((now - next_progress_at) / progress_interval) + 1) * progress_interval

        def wait_until(deadline, phase):
            # Deadline advances by the total paused duration. A pause does not
            # consume any part of the CSV profile or final/initial ramp time.
            while True:
                pause_checkpoint(phase)
                now = time.monotonic()
                heartbeat(phase)
                remaining = deadline + paused_total - now
                if remaining <= 0:
                    return
                until_heartbeat = (next_progress_at - now) if next_progress_at is not None else remaining
                time.sleep(min(remaining, 0.05, max(0.001, until_heartbeat)))
        def log(event, scheduled='', channel='', **kwargs):
            row = {'utc_time':datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                   'elapsed_s': f'{time.monotonic()-start:.6f}' if start is not None else '',
                   'event':event, 'scheduled_s':scheduled, 'channel':channel}
            row.update(kwargs)
            writer.writerow(row)
            f.flush()
            if event == 'final_state_verified' and channel in stats['final']:
                stats['final'][channel] = 'VERIFIED'
            elif event == 'final_state_error' and channel in stats['final']:
                stats['final'][channel] = 'FAILED'
            elif event == 'local_sent':
                stats['local'] = 'SENT'
            elif event == 'local_error':
                stats['local'] = 'FAILED'

        def record_lateness(scheduled_deadline):
            # Host scheduling lateness across initial ramp, profile, and final ramp.
            stats['max_lateness_ms'] = max(
                stats['max_lateness_ms'],
                max(0.0, time.monotonic() - (scheduled_deadline + paused_total)) * 1000.0)

        def print_summary():
            print('\n=== CPX400DP RUN SUMMARY ===', flush=True)
            print(f"Run status: {stats['status']}", flush=True)
            for ch in channels:
                final_action = ('original settings' if restore_flags[ch]
                                else 'OFF / 0 V / 0 A')
                print(f"Channel {ch} final state ({final_action}): {stats['final'][ch]}", flush=True)
            print(f"Maximum scheduling lateness (all phases): {stats['max_lateness_ms']:.3f} ms", flush=True)
            print('Final-state VERIFIED means programmed settings matched (not a physical-health guarantee).', flush=True)
            for ch in channels:
                print(f"Channel {ch} physical output after restoration: {stats['physical'][ch]}", flush=True)
            print(f"Output-health warnings during profile: {output_health.warnings}", flush=True)
            print(f"Expected-settling readbacks: {transient_count}; unexplained high readbacks: {implausible_count}", flush=True)
            print(f"Experiment health: {'FAILED' if fault_abort else 'WARNING' if output_health.warnings or implausible_count else 'OK'}; sustained-fault abort: {'YES' if fault_abort else 'NO'}", flush=True)
            print(f"Command traffic: {optimizer.groups} setpoint groups, {optimizer.instructions} instructions, {optimizer.suppressed} unchanged settings suppressed", flush=True)
            print(f"Command TCP send duration: mean {optimizer.total_send_ms/max(1, optimizer.groups):.3f} ms; max {optimizer.max_send_ms:.3f} ms (not PSU processing time)", flush=True)
            print(f"Measurement readbacks: {stats['readbacks_ok']} successful, "
                  f"{stats['readbacks_failed']} failed", flush=True)
            print(f"LOCAL: {stats['local']}", flush=True)
            print(f'Log: {log_path}', flush=True)
            print('============================', flush=True)

        def readbacks(sock, channels_to_read, pending, phase, schedule_s, setpoints, enables):
            """Sample across every phase on ONE monotonic time axis.

            The first sample for each phase is eligible at its boundary, but
            regular sampling is governed by a global next-readback deadline.
            Query time is included in the actual elapsed timestamp.
            """
            nonlocal next_readback_at, implausible_count, transient_count, fault_abort
            now = time.monotonic()
            if next_readback_at is not None and now + 1e-9 < next_readback_at:
                return pending
            # Advance deadlines without accumulating drift from query overhead.
            if next_readback_at is None:
                next_readback_at = now
            while next_readback_at <= now + 1e-9:
                next_readback_at += rb_interval
            for ch in channels_to_read:
                begin = time.monotonic()
                try:
                    (mv, ma), pending = measure(sock, ch, pending)
                except Exception as exc:
                    stats['readbacks_failed'] += 1
                    log('readback_error', f'{schedule_s:.6f}', ch,
                        note=f'{phase}: {exc}')
                    raise
                stats['readbacks_ok'] += 1
                latest_readings[ch] = (mv, ma)
                v, a = setpoints[ch]
                log('readback', f'{schedule_s:.6f}', ch,
                    set_voltage_v=f'{v:.3f}', current_limit_a=f'{a:.3f}',
                    requested_enable=enables.get(ch, 'hold'),
                    measured_voltage_v=f'{mv:.4f}', measured_current_a=f'{ma:.4f}',
                    readback_duration_ms=f'{(time.monotonic()-begin)*1000:.3f}',
                    note=f'phase={phase}')
                # Suspect high readback: no independent proof of a real
                # overvoltage. Report separately and retain the raw sample.
                enabled = enables.get(ch)
                if phase in ('profile', 'paused') and enabled == 1 and v >= 1.0 and mv > v + max(1.0, 0.20*v):
                    # A falling command can lead the physical output by one or
                    # two readback periods owing to PSU response/output capacitance.
                    # Compare with the *actual recently transmitted* setpoint;
                    # never excuse an excess above recent commanded voltages.
                    history = recent_setpoints.get(ch, [])
                    window = max(0.75, 3.0 * rb_interval)
                    recent = [old_v for sent_at, old_v in history
                              if 0 <= time.monotonic() - sent_at <= window]
                    settling_ceiling = max([v] + recent)
                    settling = (classify_high_readback(mv, v, history,
                                time.monotonic(), rb_interval) == 'settling')
                    last_change = next(((sent_at, old_v) for sent_at, old_v in reversed(history)
                                        if old_v > v + 0.05 and time.monotonic()-sent_at <= window), None)
                    age = (time.monotonic() - last_change[0]) if last_change else None
                    warning = (f'CH{ch}: measured {mv:.3f} V, commanded {v:.3f} V; '
                               f'recent commanded ceiling {settling_ceiling:.3f} V; '
                               f'downstep age {age*1000:.0f} ms' if age is not None else
                               f'CH{ch}: measured {mv:.3f} V, commanded {v:.3f} V; '
                               f'recent commanded ceiling {settling_ceiling:.3f} V; no recent downstep')
                    if settling:
                        transient_count += 1
                        print('[SETTLING READBACK] ' + warning, flush=True)
                        log('settling_readback', f'{schedule_s:.6f}', ch,
                            set_voltage_v=f'{v:.3f}', measured_voltage_v=f'{mv:.4f}', note=warning)
                    else:
                        implausible_count += 1
                        print('[IMPLAUSIBLE HIGH READBACK] ' + warning + '; verify independently', flush=True)
                        log('implausible_high_readback', f'{schedule_s:.6f}', ch,
                            set_voltage_v=f'{v:.3f}', measured_voltage_v=f'{mv:.4f}', note=warning)
                # Advisory only: a near-zero output despite an ON command,
                # sustained over multiple actual readbacks, resembles FAIL 2.
                # Never query, change settings, or stop on this warning.
                flag = output_health.update(ch, v, enables.get(ch), mv, phase,
                                            time.monotonic())
                if flag:
                    print('[OUTPUT HEALTH WARNING] ' + flag, flush=True)
                    log('output_health_warning', f'{schedule_s:.6f}', ch,
                        set_voltage_v=f'{v:.3f}', measured_voltage_v=f'{mv:.4f}',
                        requested_enable=enables.get(ch, ''), note=flag)
                    if abort_fault:
                        fault_abort = True
                        log('output_fault_abort', f'{schedule_s:.6f}', ch, note='Automatic abort; restoring saved settings')
                        raise OutputFaultAbort(flag)
            return pending

        with ExitStack() as socket_stack:
            from cpx400dp_discovery import connect_psu, connect_on
            sock, resolved_host, resolved_interface = connect_psu(
                host, psu_interface, discover_enabled=not no_discovery)
            sock = socket_stack.enter_context(sock)
            sock.settimeout(0.5)
            if pause_control_socket is not None:
                path = str(pause_control_socket)
                if len(path.encode()) >= 100:
                    raise ValueError('Pause control socket path too long')
                pause_listener = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                # Caller owns private directory; never replace an existing socket.
                pause_listener.bind(path)
                os.chmod(path, 0o600)
                pause_listener.setblocking(False)
                socket_stack.callback(lambda: os.path.exists(path) and os.unlink(path))
                socket_stack.enter_context(pause_listener)
                print('[PAUSE CONTROL READY] Private local socket active', flush=True)
            log('discovery', note=f'{resolved_host}:9221 interface={resolved_interface or "system route"}')
            pending = b''
            original = {}
            output_known = {ch: None for ch in channels}
            max_late = 0.0
            profile_finished = False
            interrupted = False
            captured = False
            cleanup_errors = []
            try:
                # Always snapshot selected channels: needed for initial ramp,
                # and for restoring original setpoints/output states.
                # A recently interrupted session can leave a transient stale
                # TCP/REMOTE state. Retry the double-checked read-only snapshot on a NEW socket;
                # no V/I/OP commands are sent until all selected channels agree.
                # Bounded retries take < 3 seconds in normal timeout scenarios.
                for attempt in range(1, 4):
                    try:
                        original, pending = verify_initial_snapshot(sock, channels, pending)
                        break
                    except (OSError, ConnectionError, TimeoutError, ValueError) as exc:
                        log('snapshot_retry', note=f'attempt {attempt}: {type(exc).__name__}: {exc}')
                        if attempt == 3:
                            log('snapshot_error', note=f'{type(exc).__name__}: {exc}')
                            print(f'ERROR: Initial PSU settings could not be read after '
                                  f'{attempt} attempt(s): {type(exc).__name__}: {exc}',
                                  file=sys.stderr, flush=True)
                            raise
                        print(f'Initial settings read attempt {attempt} failed '
                              f'({type(exc).__name__}: {exc}); reconnecting to retry...',
                              flush=True)
                        sock.close()
                        time.sleep(0.30)
                        sock = socket_stack.enter_context(
                            connect_on(resolved_host, resolved_interface, timeout=3))
                        sock.settimeout(0.5)
                        pending = b''
                captured = True
                for ch, (v, a, en) in original.items():
                    output_known[ch] = en
                    log('snapshot', channel=ch, set_voltage_v=f'{v:.3f}',
                        current_limit_a=f'{a:.3f}', requested_enable=en)
                    print(f'  Initial ch{ch}: {v:.3f} V, {a:.3f} A, output {"ON" if en else "OFF"}')

                # Record effective runtime configuration for reproducibility.
                log('config', note=(f'mode={mode}; interval_s={interval:g}; '
                    f'readback_interval_s={rb_interval:g}; initial_ramp_s={initial_ramp:g}; '
                    f'final_ramp_s={final_ramp:g}; overrides={bool(overrides)}'))
                pending, initial_diagnostics = collect_diagnostics(sock, pending, 'initial', log)
                # Initialise stationary hold values to the safely snapshotted settings.
                for ch, (v, a, en) in original.items():
                    last_setpoints[ch] = (v, a)
                    last_enables[ch] = en
                    prior_commanded_voltage[ch] = v
                # Set one elapsed-time origin for ALL phases, including ramps.
                start = time.monotonic()
                next_readback_at = start
                next_progress_at = start + progress_interval
                # Initial ramp finishes at t=0 of the CSV profile. Existing
                # output states are not toggled during this ramp.
                last_scheduled_send_at = None
                if initial_ramp > 0:
                    print('Running initial ramp ...')
                    heartbeat('initial_ramp', force=True)
                    ramp_start = time.monotonic()
                    ramp_pause_base = paused_total
                    first = pts[0][1]
                    for t in schedule_for(initial_ramp, interval):
                        wait_until(ramp_start + t - ramp_pause_base, 'initial_ramp')
                        record_lateness(ramp_start + t - ramp_pause_base)
                        fraction = t / initial_ramp
                        setpoints = {}
                        for ch in channels:
                            v, a = ramp_values(original[ch], first[ch], fraction)
                            setpoints[ch] = (v, a)
                            log('initial_ramp', f'{t:.6f}', ch,
                                set_voltage_v=f'{v:.3f}', current_limit_a=f'{a:.3f}',
                                requested_enable='hold')
                        commands, changed = optimizer.settings(setpoints)
                        optimizer.transmit(sock, commands, changed)
                        if commands:
                            last_scheduled_send_at = time.monotonic()
                        last_setpoints.update(setpoints)
                        pending = readbacks(sock, channels, pending, 'initial_ramp',
                                            t, setpoints, {})
                        heartbeat('initial_ramp')

                # Even if a phase ended early, separate transmitted command groups
                # at the ramp/profile boundary by at least 50 ms.
                if last_scheduled_send_at is not None:
                    gap_wait = max(0., MIN_SETPOINT_GAP_S - (time.monotonic()-last_scheduled_send_at))
                    if gap_wait: time.sleep(gap_wait)
                    log('phase_gap_guard', note=f'initial_ramp→profile: waited {gap_wait*1000:.2f} ms; commanded group spacing enforced')
                # Main CSV time_s=0 starts AFTER initial ramp.
                profile_start = time.monotonic()
                profile_pause_base = paused_total
                print('Running main profile ...', flush=True)
                heartbeat('profile', force=True)
                executed_slots = 0
                for t in schedule_for(duration, interval, (time_s for time_s, _ in pts)):
                    executed_slots += 1
                    wait_until(profile_start + t - profile_pause_base, 'profile')
                    late = max(0.0, time.monotonic() - profile_start - t - paused_total + profile_pause_base)
                    max_late = max(max_late, late)
                    stats['max_lateness_ms'] = max(stats['max_lateness_ms'], late * 1000)
                    vals = at_time(pts, t, mode)
                    commands, changed = optimizer.settings({ch: vals[ch][:2] for ch in channels})
                    for ch in channels:
                        en = vals[ch][2]
                        if en is not None and output_known[ch] != en:
                            commands.append(f'OP{ch} {en}')
                            log('output_transition', f'{profile_start-start+t:.6f}', ch,
                                requested_enable=en, note='Explicit output state transition')
                    optimizer.transmit(sock, commands, changed)
                    if commands:
                        last_scheduled_send_at = time.monotonic()
                        for ch in channels:
                            if any(cmd.startswith(f'V{ch} ') for cmd in commands):
                                history = recent_setpoints.setdefault(ch, [])
                                new_voltage = vals[ch][0]
                                previous_voltage = prior_commanded_voltage.get(ch, new_voltage)
                                # Preserve the preceding plateau level at the INSTANT
                                # of a down-step, even if it was commanded seconds ago.
                                # This allows readbacks during the first 750 ms to
                                # be recognized as plausible PSU output settling.
                                if previous_voltage > new_voltage + 0.05:
                                    history.append((last_scheduled_send_at, previous_voltage))
                                history.append((last_scheduled_send_at, new_voltage))
                                prior_commanded_voltage[ch] = new_voltage
                                recent_setpoints[ch] = history[-150:]
                    last_setpoints.update({ch: vals[ch][:2] for ch in channels})
                    for ch in channels:
                        v, a, en = vals[ch]
                        if en is not None:
                            output_known[ch] = en
                            last_enables[ch] = en
                        log('setpoint', f'{profile_start-start+t:.6f}', ch,
                            set_voltage_v=f'{v:.3f}', current_limit_a=f'{a:.3f}',
                            requested_enable='hold' if en is None else en,
                            lateness_ms=f'{late*1000:.3f}')
                    global_s = profile_start - start + t
                    pending = readbacks(sock, channels, pending, 'profile', global_s,
                                        {ch: vals[ch][:2] for ch in channels},
                                        {ch: output_known[ch] for ch in channels})
                    heartbeat('profile')
                profile_finished = True
                print(f'Finished {executed_slots} time slots; max scheduling lateness {max_late*1000:.3f} ms')
            except OutputFaultAbort as exc:
                print(f'[OUTPUT FAULT ABORT] {exc}; restoring original settings', flush=True)
                log('experiment_fault', note=str(exc))
            except KeyboardInterrupt:
                interrupted = True
                print('\nInterrupted by Ctrl+C; attempting configured final-state cleanup ...', flush=True)
                log('interrupted', note='Ctrl+C received; starting final-state cleanup')
            finally:
                # Cleanup is attempted even after Ctrl+C and query errors.
                # On errors, skip the leisurely final ramp and promptly restore.
                # A saved ON output is never deliberately disabled for a ramp.
                if captured:
                    if profile_finished and not fault_abort and final_ramp > 0:
                        restore_ch = [ch for ch in channels if restore_flags[ch]]
                        if restore_ch:
                            try:
                                print('Running final ramp to saved settings ...')
                                heartbeat('final_ramp', force=True)
                                last = at_time(pts, duration, mode)
                                if last_scheduled_send_at is not None:
                                    gap_wait = max(0., MIN_SETPOINT_GAP_S - (time.monotonic()-last_scheduled_send_at))
                                    if gap_wait: time.sleep(gap_wait)
                                    log('phase_gap_guard', note=f'profile→final_ramp: waited {gap_wait*1000:.2f} ms; commanded group spacing enforced')
                                ramp_start = time.monotonic()
                                ramp_pause_base = paused_total
                                for t in schedule_for(final_ramp, interval):
                                    wait_until(ramp_start + t - ramp_pause_base, 'final_ramp')
                                    record_lateness(ramp_start + t - ramp_pause_base)
                                    fraction = t / final_ramp
                                    setpoints = {}
                                    for ch in restore_ch:
                                        v, a = ramp_values(last[ch], original[ch], fraction)
                                        setpoints[ch] = (v, a)
                                        log('final_ramp', f'{ramp_start-start+t:.6f}', ch,
                                            set_voltage_v=f'{v:.3f}', current_limit_a=f'{a:.3f}',
                                            requested_enable='hold')
                                    commands, changed = optimizer.settings(setpoints)
                                    optimizer.transmit(sock, commands, changed)
                                    last_setpoints.update(setpoints)
                                    pending = readbacks(sock, restore_ch, pending,
                                                        'final_ramp', ramp_start-start+t,
                                                        setpoints, {})
                                    heartbeat('final_ramp')
                            except BaseException as exc:
                                cleanup_errors.append(f'final ramp failed: {exc}')
                                log('final_ramp_error', note=str(exc))
                    print('Verifying and restoring final settings ...', flush=True)
                    heartbeat('restoration', force=True)
                    try:
                        cleanup_errors += finish_channels(sock, channels, original,
                                                           restore_flags, pending, log)
                    except BaseException as exc:
                        cleanup_errors.append(f'final state failed: {exc}')
                        log('final_state_error', note=str(exc))
                    # Physical output check is advisory. It must happen before
                    # LOCAL and cannot overturn programmed-restoration status.
                    try:
                        stats['physical'], pending = verify_physical_outputs(
                            sock, channels, original, restore_flags, pending, log)
                    except BaseException as exc:
                        print(f'[OUTPUT HEALTH WARNING] Physical check unavailable: {exc}', flush=True)
                        for ch in channels:
                            stats['physical'][ch] = 'NOT CHECKED (error)'
                else:
                    cleanup_errors.append('Initial snapshot failed: unable to safely restore original state')
                    log('final_state_error', note=cleanup_errors[-1])
                # Final diagnostics occur after restoration/physical verification,
                # immediately before LOCAL. A failure here cannot block LOCAL.
                try:
                    pending, final_diagnostics = collect_diagnostics(sock, pending, 'final', log)
                except BaseException as exc:
                    log('diagnostic_error', note=f'final snapshot unexpectedly failed: {exc}')
                # LAST instrument command. Never query after LOCAL: even one
                # subsequent query would re-enter REMOTE mode.
                try:
                    send(sock, 'LOCAL')
                    log('local_sent', note='LOCAL was sent as last instrument command; front-panel LOCK may remain active')
                    print('LOCAL command sent; front-panel LOCK may still need to be cancelled manually.')
                except BaseException as exc:
                    cleanup_errors.append(f'LOCAL command failed: {exc}')
                    log('local_error', note=str(exc))
                log('command_summary', note=(
                    f'setting_groups={optimizer.groups}; setting_instructions={optimizer.instructions}; '
                    f'unchanged_suppressed={optimizer.suppressed}; '
                    f'mean_tcp_send_ms={optimizer.total_send_ms/max(1,optimizer.groups):.4f}; '
                    f'max_tcp_send_ms={optimizer.max_send_ms:.4f}; '
                    'TCP duration is not instrument processing time'))
                stats['status'] = ('ERROR — cleanup not fully verified' if cleanup_errors
                                   else 'ABORTED (output fault) — cleanup verified' if fault_abort
                                   else 'INTERRUPTED — cleanup verified' if interrupted
                                   else 'COMPLETED — cleanup verified' if profile_finished
                                   else 'ERROR — cleanup verified')
                print_summary()
                if cleanup_errors:
                    print('WARNING: ' + '; '.join(cleanup_errors), file=sys.stderr)
                    raise RuntimeError('Cleanup not fully verified; check PSU settings and LOCAL mode')
            if fault_abort:
                print('ABORTED: sustained output fault; configured final states restored; LOCAL sent.', flush=True)
                return 2
            if interrupted:
                print('INTERRUPTED: configured final states verified; LOCAL command sent. Log saved.', flush=True)
                return 130
    print('Logging complete.')
    return 0


def report_options(path):
    # Parse report options independently, without changing the verified PSU engine.
    opts = {'generate_report': 'true', 'report_layout': 'separate'}
    with path.open(encoding='utf-8-sig') as f:
        for line in f:
            text = line.lstrip()
            if not text.startswith('#'):
                break
            item = text[1:].strip().rstrip(',').strip()
            if '=' in item:
                key, value = [x.strip() for x in item.split('=', 1)]
                if key in opts:
                    opts[key] = value.lower()
    if opts['generate_report'] not in ('true', 'false'):
        raise ValueError('generate_report must be true or false')
    if opts['report_layout'] not in ('separate', 'combined', 'power'):
        raise ValueError('report_layout must be separate, combined, or power')
    return opts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', type=Path)
    parser.add_argument('--output-dir', type=Path, default=None,
                        help='Directory for measurement CSV and HTML report; default: profile directory')
    parser.add_argument('--channels', default=None, help='Selected subset of channels defined in the CSV, e.g. 1 or 1,2')
    parser.add_argument('--mode', choices=['linear', 'step'], default=None)
    parser.add_argument('--interval-s', type=float, default=None)
    parser.add_argument('--readback-interval-s', type=float, default=None)
    parser.add_argument('--initial-ramp-s', type=float, default=None)
    parser.add_argument('--final-ramp-s', type=float, default=None)
    parser.add_argument('--run-id', default=None, help='Optional run identifier for unique output files')
    parser.add_argument('--psu-ip', default=None, help='Override CSV IP for discovery or manual connection')
    parser.add_argument('--psu-interface', default=None, help='Force a Linux Ethernet interface')
    parser.add_argument('--pause-control-socket', default=None, help='Private UNIX datagram socket for paused-profile manual control')
    parser.add_argument('--no-discovery', action='store_true', help='Skip read-only *IDN? discovery and use specified IP/interface')
    parser.add_argument('--preview', action='store_true',
                        help='Generate an instant offline profile preview; never connect to the PSU')
    args = parser.parse_args()
    profile = args.profile.resolve()
    overrides = {key: value for key, value in {
        'channels': args.channels, 'mode': args.mode, 'interval_s': args.interval_s,
        'readback_interval_s': args.readback_interval_s,
        'initial_ramp_s': args.initial_ramp_s,
        'final_ramp_s': args.final_ramp_s}.items() if value is not None}
    if args.preview:
        try:
            from cpx400dp_preview import generate_preview
            target = None
            if args.output_dir is not None:
                folder = args.output_dir.expanduser().resolve()
                if not folder.is_dir():
                    raise ValueError(f'Output directory does not exist: {folder}')
                target = folder / (profile.stem + '_preview.html')
            output = generate_preview(profile, output_path=target,
                                      load_profile=load_profile, at_time=at_time, overrides=overrides)
            print(f'Profile preview: {output}')
            return 0
        except (OSError, ValueError, KeyError, ImportError) as exc:
            print(f'PREVIEW ERROR: {exc}', file=sys.stderr)
            return 1
    try:
        report_cfg = report_options(profile)
        log_path = load_profile(profile, overrides=overrides)[5]
        if args.output_dir is not None:
            folder = args.output_dir.expanduser().resolve()
            if not folder.is_dir():
                raise ValueError(f'Output directory does not exist: {folder}')
            log_path = folder / log_path.name
            if log_path.resolve() == profile.resolve():
                raise ValueError('Measurement log must not overwrite the input profile')
    except (OSError, ValueError, KeyError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    run_id = args.run_id or datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    log_path = log_path.with_name(f'{log_path.stem}_{run_id}{log_path.suffix}')
    previous_mtime = log_path.stat().st_mtime_ns if log_path.exists() else None
    code = 0
    try:
        connection_options = {}
        if args.psu_ip is not None: connection_options['psu_ip'] = args.psu_ip
        if args.psu_interface is not None: connection_options['psu_interface'] = args.psu_interface
        if args.no_discovery: connection_options['no_discovery'] = True
        if args.pause_control_socket: connection_options['pause_control_socket'] = args.pause_control_socket
        code = execute(profile, output_dir=args.output_dir, overrides=overrides,
                       run_id=run_id, **connection_options)
    except KeyboardInterrupt:
        print('INTERRUPTED: Ctrl+C during setup or cleanup; PSU final state is not guaranteed. Check the instrument.', file=sys.stderr)
        code = 130
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        code = 1
    # Plotting happens in a separate process only after the instrument run has
    # finished. A reporting problem never alters the run's return code.
    if report_cfg['generate_report'] == 'true' and log_path.exists() and (previous_mtime is None or log_path.stat().st_mtime_ns != previous_mtime):
        # The initial snapshot may fail before any channel readings or profile
        # events are logged. That is a valid failed run, not a plotting error.
        try:
            with log_path.open(newline='', encoding='utf-8-sig') as f:
                events = list(csv.DictReader(f))
            has_measurements = any(row.get('event') == 'readback' for row in events)
        except (OSError, csv.Error) as exc:
            print(f'WARNING: Cannot inspect measurement log for report: {exc}', file=sys.stderr)
            has_measurements = False
        if not has_measurements:
            print('REPORT SKIPPED: no successful PSU readbacks were recorded; '
                  'nothing to plot.', flush=True)
        else:
            helper = Path(__file__).with_name('cpx400dp_report.py')
            try:
                result = subprocess.run(
                    [sys.executable, str(helper), str(log_path), '--layout', report_cfg['report_layout']],
                    capture_output=True, text=True, check=True)
                if result.stdout.strip():
                    print(f'HTML report: {result.stdout.strip()}', flush=True)
            except (OSError, subprocess.CalledProcessError) as exc:
                detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
                print(f'WARNING: HTML report could not be generated: {detail}', file=sys.stderr)
    return code


if __name__ == '__main__':
    sys.exit(main())
