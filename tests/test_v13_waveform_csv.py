"""Waveform-only CSV compatibility and constraints. No hardware required."""
import tempfile
import unittest
from pathlib import Path
from cpx400dp_run_enhanced import load_profile
from cpx400dp_preview import profile_summary


class WaveformOnlyTests(unittest.TestCase):
    def write(self, data):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = Path(self.tmp.name) / 'wave.csv'
        p.write_text(data)
        return p

    def test_waveform_without_metadata(self):
        p = self.write('time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable\n'
                       '0,1,1,0\n0.25,2,1,1\n1,1,1,0\n')
        host, channels, mode, interval, rb, log, pts, restore, *_ = load_profile(p)
        self.assertEqual(channels, [1])
        self.assertEqual(mode, 'linear')
        self.assertEqual((interval, rb), (.05, .25))
        self.assertEqual(restore, {1:True})
        self.assertEqual(log.name, 'wave_measurements.csv')
        self.assertEqual(len(pts), 3)

    def test_gui_settings_overrides_waveform_defaults(self):
        p = self.write('time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable\n'
                       '0,1,1,0\n0.25,2,1,1\n1,1,1,0\n')
        r = load_profile(p, {'mode':'step','readback_interval_s': .1,
                             'initial_ramp_s':0,'final_ramp_s':2.0})
        self.assertEqual((r[2], r[4], r[9]), ('step', .1, 2.0))

    def test_legacy_compatibility(self):
        p = Path(__file__).resolve().parents[1] / 'profiles' / '15.csv'
        raw = load_profile(p)
        self.assertEqual(raw[4], .25)
        self.assertEqual(raw[9], 2.0)
        gui = load_profile(p, {'readback_interval_s':.1, 'final_ramp_s':0})
        self.assertEqual(gui[4], .1)
        self.assertEqual(gui[9], 0)

    def test_infer_two_channels(self):
        p = self.write('time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable,'
                       'ch2_voltage_v,ch2_current_limit_a,ch2_enable\n'
                       '0,1,1,0,2,.5,0\n1,2,1,1,3,.5,1\n')
        self.assertEqual(load_profile(p)[1], [1,2])
        self.assertEqual(load_profile(p, {'channels':'2'})[1], [2])

    def test_invalid_channel_rejected(self):
        p = self.write('time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable\n'
                       '0,1,1,0\n1,2,1,1\n')
        with self.assertRaisesRegex(ValueError, 'missing from'):
            load_profile(p, {'channels':'2'})

    def test_invalid_timestamp_rejected(self):
        p = self.write('time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable\n'
                       '.5,1,1,0\n1,2,1,1\n')
        with self.assertRaisesRegex(ValueError, 'timestamp'):
            load_profile(p)

    def test_invalid_voltage_rejected(self):
        p = self.write('time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable\n'
                       '0,1,1,0\n1,70,1,1\n')
        with self.assertRaisesRegex(ValueError, '0–60 V'):
            load_profile(p)

    def test_minimum_gap_retained(self):
        p = self.write('time_s,ch1_voltage_v,ch1_current_limit_a,ch1_enable\n'
                       '0,1,1,0\n.020,2,1,1\n1,1,1,0\n')
        with self.assertRaisesRegex(ValueError, 'spacing'):
            profile_summary(p)

if __name__=='__main__': unittest.main()
