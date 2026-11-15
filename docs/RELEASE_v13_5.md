# v13.5 — development milestone (not hardware-validated release)

**Branch:** `dev`  
**Predecessor:** v13.4 development changes.  
**Evidence:** Current `scripts/cpx400dp_gui.py`, `tests/test_v13_2_manual_confirmation.py`, and recovered November 2026 conversation. No tag or independent hardware validation established by this document.

## Behaviour present in current dev source

- Clicking **Enable output** in standalone Manual Control now dispatches without a confirmation prompt.
- Clicking **Enable output** while controlling a paused profile also dispatches without confirmation (introduced in v13.2).
- Clicking **Resume paused profile** requires no confirmation (v13.4 change).
- Enable and Disable output buttons use the most recently received PSU programmed output state: redundant commands are disabled.
- Bright green ON, red OFF, and grey UNKNOWN output indicators remain.
- Commands continue to be validated/read back; output-enable confirmation removal does **not** bypass command verification.
- Displayed manual V/A values remain at two decimals; SCPI/programmed values and measurement log precision are maintained separately.
- Pause-point restoration and verification, single runner transport ownership, cleanup, and `LOCAL` last remain requirements.

## Validation status

- Historical report for v13.4: **94 offline tests passed** at that stage; the v13.4 documentation stated physical PSU/Qt visual validation was pending.
- Historical report for v13.5: **six focused handler checks passed**. The previous development conversation explicitly stated the **complete offline regression suite was not run** in that session.
- The user subsequently reported that earlier manual-control changes worked on their hardware, but this does **not** establish a documented comprehensive v13.5 hardware regression.
- During the 2026-11-15 documentation reconciliation: **source reviewed, tests not executed, physical hardware not exercised**.

Do not promote v13.5 into a validated stable release, tag it as hardware-validated or merge it to `main` solely based on the historic test counts.

## Remaining release gates

1. Run complete offline suite at current `dev` HEAD and record SHA and counts.
2. Verify standalone/manual and paused-profile ON/OFF, disabled redundant buttons, and prominent output indicators on physical CPX400DP.
3. Verify Resume restoration and timing, Stop during pause, and `LOCAL` final-command behaviour at low power.
4. Archive dated CSV, HTML report and console log for each hardware validation; record Git SHA, load and outcome.
5. Only then decide whether to tag/merge an explicitly validated release.
