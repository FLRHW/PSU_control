# Long-duration recording storage and recovery (v13.6)

## Runtime storage warning

The runner now performs a read-only filesystem free-space check while
waiting for setpoints and while reporting heartbeat progress. It uses
scripts/cpx400dp_storage.py DiskSpaceMonitor and does not contact the
PSU. The check is rate-limited to once per 30 s. When remaining space is
at or below the advisory 512 MiB reserve, the console prints
[STORAGE WARNING], repeated at most once per five minutes. A failed
disk query does not interrupt instrument cleanup.

This is a **warning**, not a safety mechanism or disk reservation.
The runner continues instead of silently changing outputs. If the
warning appears, the operator should judge whether to use the GUI's
normal Stop/safe-cleanup workflow. Filling the disk may prevent future
CSV writes or HTML generation; a storage advisory cannot guarantee
safe unattended behaviour.

The pre-run disk-space estimate remains advisory and is not a reliable
hard upper bound, especially if unplanned manual events or extra
applications consume disk space.

## Interrupted-recording audit

The new command below inspects a saved measurement CSV without
opening an instrument socket, editing the CSV, or deleting anything:

    /usr/bin/python3 scripts/cpx400dp_recording_audit.py /path/to/run_measurements.csv

Or inspect all matching recordings in one output folder:

    /usr/bin/python3 scripts/cpx400dp_recording_audit.py /path/to/output/folder

Append --json for machine-readable inspection.

It scans row by row and reports logged successful/failed readbacks,
observed channels, final_state_verified events, whether a local_sent
event was logged, interrupt/fault markers, last event and timestamp.

**Critical:** even when a CSV contains final_state_verified and
local_sent, those are logged events, not independent proof of actual
terminal voltage, enabled output, or LOCAL front-panel state.
Unexpected host shutdown, SIGKILL, USB/network failure, or full-disk
write failure can leave an unverified instrument state. The operator
must inspect the PSU front panel and outputs before another run.
The inspector never attempts automated reconnection or corrective
commands and never assumes a safe state.

## Optional checked archive (no deletion)

Use the following command only after the recording has finished:

    /usr/bin/python3 scripts/cpx400dp_archive.py reports/example_measurements.csv

It creates `example_measurements_archive.zip` next to the original, with
the raw CSV plus any matching report HTML, its `_report_data/` folder and
console log. Use `--output /safe/backup/location.zip` to choose a different
destination. The source files are never deleted, and existing archives
are never overwritten. A temporary ZIP is checked against SHA-256
checksums and published atomically on supported Linux filesystems.
The original CSV remains the authoritative record.

**Do not use it on a still-running experiment**: an incomplete or
changing measurement log may be inconsistent even if a copy succeeds.
This provides a manual retention workflow, not an automatic backup,
power-loss recovery or long-term bit-rot protection mechanism.

## File retention

The raw measurement CSV is the authoritative data source; do not
overwrite or auto-delete it. For large reports, retain the matching
_report.html and _report_data folder together or regenerate the report
from the raw CSV.

No automatic deletion/rotation policy is introduced; choose storage
retention and backup policy explicitly in a later decision.
Multi-day unattended runs, full-disk recovery and real PSU endurance
have not been validated on hardware.

## Tests

Offline unit tests cover disk polling cadence, low-space warning
suppression and exception handling; the audit's complete/incomplete,
interrupted/fault and synthetic-data classification; and parsing of
all three sparse preview profiles. GitHub CI passing is not evidence
of hardware power-loss recovery or durable recording under full disk.
