#!/usr/bin/env python3
"""Small Qt-independent utilities for the CPX400DP desktop GUI.

No PSU communication takes place in this module.
"""
from pathlib import Path
from html.parser import HTMLParser
import base64
import re

RUNNER_NAME = 'cpx400dp_run_enhanced.py'
PREVIEW_NAME = 'cpx400dp_preview.py'
REPORT_NAME = 'cpx400dp_report.py'


def require_files(folder):
    folder = Path(folder)
    missing = [name for name in (RUNNER_NAME, PREVIEW_NAME, REPORT_NAME)
               if not (folder / name).is_file()]
    if missing:
        raise FileNotFoundError('Missing companion files: ' + ', '.join(missing))


def resolve_output(filename, cwd):
    """Runner resolves relative output paths in its working directory."""
    result = Path(filename.strip())
    return result if result.is_absolute() else Path(cwd) / result


class _PlotParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag != 'img':
            return
        props = dict(attrs)
        source = props.get('src', '')
        if source.startswith('data:image/png;base64,'):
            encoded = source.split(',', 1)[1]
            try:
                data = base64.b64decode(encoded, validate=True)
            except (ValueError, base64.binascii.Error):
                return
            self.images.append((props.get('alt', 'Profile plot'), data))


def embedded_preview_plots(preview_html):
    """Extract the existing preview's PNG plots for native Qt rendering."""
    parser = _PlotParser()
    parser.feed(Path(preview_html).read_text(encoding='utf-8'))
    if not parser.images:
        raise ValueError('No embedded preview plots found')
    return parser.images


PROGRESS_RE = re.compile(r'\[PROGRESS\]\s+([\d.]+)/([\d.]+)s\s+\(~([\d.]+)s remaining\)')


def parse_progress(line):
    match = PROGRESS_RE.search(line)
    if not match:
        return None
    elapsed, total, remaining = (float(v) for v in match.groups())
    return {'elapsed_s': elapsed, 'total_s': total, 'remaining_s': remaining,
            'percent': min(100, max(0, round(100 * elapsed / total))) if total else 0}


def parse_report_path(line, cwd):
    if not line.startswith('HTML report: '):
        return None
    return resolve_output(line.split(': ', 1)[1], cwd)


def parse_profile_preview_path(line, cwd):
    if not line.startswith('Profile preview: '):
        return None
    return resolve_output(line.split(': ', 1)[1], cwd)

HEARTBEAT_RE = re.compile(r'\[PROGRESS\]\s+([\d.]+)/([\d.]+)s\s+\(~([\d.]+)s remaining\)\s*\|\s*([^|]+)')
READING_RE = re.compile(r'\bch([12]):\s*([\d.]+)\s*V,\s*([\d.]+)\s*A\b')
FINAL_RE = re.compile(r'^Channel ([12]) final state \(original settings\):\s*(VERIFIED|NOT VERIFIED)\s*$',re.I)


def parse_heartbeat(line):
    """Return phase, progress and most recent values (no additional PSU queries)."""
    match = HEARTBEAT_RE.search(line)
    if not match:
        return None
    elapsed, total, remaining = map(float, match.group(1, 2, 3))
    readings = {int(ch): {'voltage_v': float(v), 'current_a': float(a)}
                for ch, v, a in READING_RE.findall(line)}
    return {'elapsed_s': elapsed, 'total_s': total,
            'remaining_s': remaining,
            'percent': min(100, max(0, round(100*elapsed/total))) if total else 0,
            'phase': match.group(4).strip(), 'readings': readings}


def parse_final_verification(line):
    match = FINAL_RE.match(line.strip())
    if not match:
        return None
    return int(match.group(1)), match.group(2).upper() == 'VERIFIED'


def classify_run(exit_code, summary, final_states):
    """Explicitly differentiate intentional SIGINT and an error. Pure and testable."""
    summary = (summary or '').lower()
    all_verified = bool(final_states) and all(final_states.values())
    if exit_code == 0 and 'completed' in summary and 'cleanup verified' in summary and all_verified:
        return 'completed', 'Completed — restoration verified'
    if exit_code == 130 and 'interrupted' in summary and 'cleanup verified' in summary and all_verified:
        return 'stopped', 'Stopped by user — restoration verified'
    return 'error', f'Run error (exit code {exit_code}) — check PSU and restoration status'
