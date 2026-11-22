"""Offline interruption audit: no PSU, network, file mutation or cleanup."""
import csv
import tempfile
import unittest
from pathlib import Path
from cpx400dp_recording_audit import audit, main

FIELDS = ['utc_time', 'elapsed_s', 'event', 'channel', 'note']


def make(path, events):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for event, ch, note in events:
            w.writerow({'event': event, 'channel': ch, 'note': note})


class RecordingAuditTests(unittest.TestCase):
    def test_complete_log_is_logged_only_not_physical_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'run_measurements.csv'
            make(p, [('readback', '1', ''), ('final_state_verified', '1', ''),
                     ('local_sent', '', '')])
            prior = p.read_bytes()
            found = audit(p)
            self.assertIn('NOT PHYSICAL CONFIRMATION', found['status'])
            self.assertEqual(found['readbacks'], 1)
            self.assertEqual(found['final_state_verified'], [1])
            self.assertEqual(p.read_bytes(), prior)

    def test_missing_local_or_final_is_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'incomplete.csv'
            make(p, [('readback', '1', '')])
            found = audit(p)
            self.assertIn('INCOMPLETE', found['status'])
            self.assertFalse(found['local_command_logged'])

    def test_interruption_and_fault_are_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'interrupted.csv'
            make(p, [('readback', '2', ''), ('interrupted', '', ''),
                     ('final_state_verified', '2', ''), ('local_sent', '', '')])
            audited = audit(p)
            self.assertIn('INTERRUPTED — LOGGED CLEANUP VERIFIED', audited['status'])
            self.assertTrue(audited['cleanup_logged_after_interruption'])
            make(p, [('readback', '1', ''), ('output_fault_abort', '', ''),
                     ('final_state_verified', '1', ''), ('local_sent', '', '')])
            self.assertIn('FAULT ABORT — LOGGED CLEANUP VERIFIED', audit(p)['status'])

    def test_cleanup_must_follow_last_interruption_for_each_channel(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'stale_cleanup.csv'
            make(p, [('readback', '1', ''), ('readback', '2', ''),
                     ('final_state_verified', '1', ''),
                     ('final_state_verified', '2', ''),
                     ('local_sent', '', ''), ('interrupted', '', '')])
            found = audit(p)
            self.assertIn('CLEANUP NOT CONFIRMED BY LOG', found['status'])
            self.assertFalse(found['cleanup_logged_after_interruption'])
            make(p, [('interrupted', '', ''),
                     ('final_state_verified', '1', ''),
                     ('local_sent', '', ''), ('readback', '2', '')])
            self.assertIn('CLEANUP NOT CONFIRMED BY LOG', audit(p)['status'])
            make(p, [('interrupted', '', ''),
                     ('final_state_verified', '1', ''),
                     ('final_state_verified', '2', ''),
                     ('local_sent', '', '')])
            self.assertTrue(audit(p)['cleanup_logged_after_interruption'])

    def test_empty_log_reported_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'empty.csv'
            p.write_text(','.join(FIELDS) + '\\n')
            self.assertIn('EMPTY LOG', audit(p)['status'])

    def test_synthetic_data_never_claims_hardware_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'synthetic.csv'
            make(p, [('config', '', 'SYNTHETIC MOCK MEASUREMENTS'),
                     ('readback', '1', ''), ('final_state_verified', '1', ''),
                     ('local_sent', '', '')])
            self.assertIn('SYNTHETIC', audit(p)['status'])

    def test_header_error_and_cli_return_value(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'broken.csv'
            p.write_text('event\nreadback\n')
            self.assertIsNotNone(audit(p)['inspection_error'])
            self.assertEqual(main([str(p), '--json']), 1)


if __name__ == '__main__':
    unittest.main()
