"""CPX400DP LSR event decoding requires conservative unknown handling."""
import unittest
from cpx400dp_regulation import decode_limit_event


class RegulationEventTests(unittest.TestCase):
    def test_unambiguous_status_events(self):
        self.assertEqual(decode_limit_event('1', True), 'CV')
        self.assertEqual(decode_limit_event('2', True), 'CC')
        self.assertEqual(decode_limit_event('0x10', True), 'UNREG')

    def test_read_clear_zero_retains_last_observed_mode(self):
        self.assertEqual(decode_limit_event('0', True, 'CV'), 'CV')
        self.assertIsNone(decode_limit_event('0', True))
        self.assertIsNone(decode_limit_event('0', False, 'CV'))

    def test_ambiguous_and_fault_conditions_are_unknown(self):
        for value in ('3','0x12'):
            self.assertIsNone(decode_limit_event(value,True,'CV'))
        for value in ('0x41','0x08','0x04'):
            self.assertEqual(decode_limit_event(value,True,'CV'),'FAULT')
        self.assertIsNone(decode_limit_event('1',False,'CC'))

    def test_invalid_status_rejected(self):
        for value in ('','oops','-1','256','0b10'):
            with self.assertRaises(ValueError):
                decode_limit_event(value,True)


if __name__=='__main__':
    unittest.main()
