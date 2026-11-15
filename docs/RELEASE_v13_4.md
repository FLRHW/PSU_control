# v13.4 development changes

- Both manual control channels display a prominent status indicator: green `OUTPUT ON`, red `OUTPUT OFF`, grey `OUTPUT UNKNOWN` until readback.
- Enable Output is active only if the most recently received programmed output state is OFF; Disable Output is active only if it is ON. Until a state is known, neither command is enabled.
- Resuming a paused profile after manual control no longer presents an additional confirmation dialog. The runner still reasserts and verifies the held profile state before advancing profile time.
- Two decimal places are retained for voltage and current displays.
- The existing confirmation before enabling output in *standalone* manual mode remains.

Offline regression suite: 94 tests passed in the development environment. Physical PSU and Qt visual validation outstanding. `main` remains unchanged.
