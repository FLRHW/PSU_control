# CSV waveform examples

These files are ready to open in the CPX400DP GUI. They have **no host-specific IP address or configuration preamble**; the GUI determines connection settings, interpolation mode, timing and ramps. The runner defaults to restoring the original programmed channel settings.

| File | Duration | Peak voltage | Output state in the waveform |
| --- | ---: | --- | --- |
| `ch1_90s_3v.csv` | 90 s | CH1 3 V | ON during profile, OFF at final keyframe |
| `ch1_90s_8v_cc.csv` | 90 s | CH1 8 V | ON during profile, OFF at final keyframe |
| `dual_90s.csv` | 90 s | CH1 4 V, CH2 3 V | Both OFF |
| `ch1_24h.csv` | 24 hours | CH1 2 V | OFF |
| `dual_7d.csv` | 7 days | CH1 3 V, CH2 1.5 V | Both OFF |
| `dual_1000h.csv` | 1000 hours | CH1 2 V, CH2 1 V | Both OFF |

The `ch1_90s_8v_cc.csv` waveform includes a 6 V setpoint with a reduced 0.15 A current limit from 40–50 seconds to illustrate current limiting. Whether the instrument enters CC depends on the connected load.

For step-shaped operation, select **step** in the GUI; for interpolated ramps, select **linear**. The long-duration waveforms are sparse but will use the GUI's currently configured update/readback intervals if run. Review those settings for the intended duration.

For general operating precautions, see the repository [README](../../README.md#safety-and-responsibility).
