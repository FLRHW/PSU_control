CPX400DP GUI v13.2 — paused-manual usability patch

Changes versus v13.1:
- Enable output while controlling a PAUSED profile no longer displays a Yes/No confirmation.
- Standalone Manual Control continues to show the safety confirmation before enabling output.
- Routine successful paused-manual command verification appears in the runner console, not in the Manual Control status label. The status label remains for connection/mode messages and warnings.
- Paused-manual success lines now format setpoints to three decimals (e.g. 10.500 instead of 10.499999999999995). Verification and error handling remain unchanged.
- Existing pause, readback verification, restoration on Resume and LOCAL-last behaviour are unchanged.

Run: use the existing launch script from the extracted application folder.
Hardware status: regression tests passed; the revised confirmation/UI flow needs testing on Kubuntu/physical PSU.
