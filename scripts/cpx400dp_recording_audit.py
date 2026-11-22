#!/usr/bin/env python3
"""Read-only inspection of CPX400DP CSV recordings after interruption.

This cannot tell whether outputs are physically safe. If a run lost power
or was killed, inspect the instrument locally before connecting again.
No deletion, modification, network access or SCPI commands.
"""
import argparse
import csv
import json
from pathlib import Path


def audit(path):
    """Inspect log incrementally; never load all rows into RAM."""
    path = Path(path)
    result = {
        'file': str(path), 'status': 'INCOMPLETE/UNVERIFIED',
        'total_rows': 0, 'readbacks': 0, 'readback_errors': 0,
        'channels_seen': [], 'final_state_verified': [],
        'local_command_logged': False, 'interrupted_logged': False,
        'fault_abort_logged': False, 'synthetic_data': False,
        'last_event': '', 'last_elapsed_s': None,
        'last_utc_time': None, 'inspection_error': None
    }
    seen, verified = set(), set()
    verification_row = {}
    last_local_row = -1
    last_abort_row = -1
    try:
        with path.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            needed = {'event', 'channel', 'elapsed_s', 'utc_time'}
            if not reader.fieldnames or not needed.issubset(reader.fieldnames):
                result['inspection_error'] = 'Missing essential measurement CSV columns'
                return result
            for row in reader:
                result['total_rows'] += 1
                event = str(row.get('event') or '')
                ch = (row.get('channel') or '').strip()
                if ch in ('1', '2'):
                    seen.add(int(ch))
                if event == 'final_state_verified' and ch in ('1', '2'):
                    verified.add(int(ch))
                    verification_row[int(ch)] = result['total_rows']
                result['readbacks'] += (event == 'readback')
                result['readback_errors'] += (event == 'readback_error')
                result['local_command_logged'] |= event == 'local_sent'
                result['interrupted_logged'] |= event == 'interrupted'
                result['fault_abort_logged'] |= event == 'output_fault_abort'
                if event in ('interrupted', 'output_fault_abort'):
                    last_abort_row = result['total_rows']
                if event == 'local_sent':
                    last_local_row = result['total_rows']
                if event == 'config' and 'SYNTHETIC' in str(row.get('note') or '').upper():
                    result['synthetic_data'] = True
                result['last_event'] = event
                if (row.get('elapsed_s') or '').strip():
                    result['last_elapsed_s'] = row['elapsed_s']
                if (row.get('utc_time') or '').strip():
                    result['last_utc_time'] = row['utc_time']
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        result['inspection_error'] = f'{type(exc).__name__}: {exc}'
    result['channels_seen'] = sorted(seen)
    result['final_state_verified'] = sorted(verified)
    cleanup_after_abort = (
        last_abort_row >= 0 and last_local_row > last_abort_row and
        bool(seen) and all(verification_row.get(ch, -1) > last_abort_row for ch in seen))
    result['cleanup_logged_after_interruption'] = bool(cleanup_after_abort)
    if result['inspection_error']:
        result['status'] = 'INSPECTION ERROR / STATE UNKNOWN'
    elif result['total_rows'] == 0:
        result['status'] = 'EMPTY LOG (NO EVENTS RECORDED)'
    elif result['fault_abort_logged']:
        result['status'] = ('FAULT ABORT — LOGGED CLEANUP VERIFIED (NOT PHYSICAL CONFIRMATION)'
                            if cleanup_after_abort else 'FAULT ABORT — CLEANUP NOT CONFIRMED BY LOG')
    elif result['interrupted_logged']:
        result['status'] = ('INTERRUPTED — LOGGED CLEANUP VERIFIED (NOT PHYSICAL CONFIRMATION)'
                            if cleanup_after_abort else 'INTERRUPTED — CLEANUP NOT CONFIRMED BY LOG')
    elif seen and seen <= verified and result['local_command_logged']:
        result['status'] = 'LOGGED FINAL VERIFICATION (NOT PHYSICAL CONFIRMATION)'
    if result['synthetic_data']:
        result['status'] = 'SYNTHETIC DATA / NO HARDWARE STATE IMPLIED'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', type=Path, help='Measurement CSV files, or folders to inspect')
    parser.add_argument('--json', action='store_true', help='Machine-readable report')
    args = parser.parse_args(argv)
    files = []
    for target in args.paths:
        if target.is_dir():
            files.extend(sorted(target.glob('*_measurements*.csv')))
        else:
            files.append(target)
    reports = [audit(p) for p in files]
    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        for item in reports:
            print(item['file'])
            print('  ' + item['status'])
            print(f"  Rows: {item['total_rows']}; readbacks: {item['readbacks']}; "
                  f"errors: {item['readback_errors']}")
            print(f"  Channels present: {item['channels_seen']}; final-state events: "
                  f"{item['final_state_verified']}; LOCAL sent event: "
                  f"{item['local_command_logged']}")
            if item['inspection_error']:
                print('  INSPECTION ERROR: ' + item['inspection_error'])
    print('IMPORTANT: CSV events never prove actual electrical output or LOCAL state; '
          'check instrument front panel after an unexpected interruption.')
    return 0 if reports and all(x['inspection_error'] is None for x in reports) else 1


if __name__ == '__main__':
    raise SystemExit(main())
