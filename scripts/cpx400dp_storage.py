"""Read-only, advisory storage forecast for CPX400DP measurement logging.

This estimate is intentionally conservative and is NOT a disk reservation
or a guarantee about later disk consumption. Never contacts the PSU.
"""
from pathlib import Path
import math
import shutil

# Approximate upper-budget per CSV event, allowing verbose timestamps/notes.
BYTES_PER_EVENT = 512
RESERVE_BYTES = 512 * 1024 * 1024


def storage_forecast(output_path, duration_s, interval_s, readback_interval_s,
                     channel_count, disk_usage=shutil.disk_usage):
    """Return a human-readable warning or None; fail open on OS probe errors.

    A fixed size estimate accounts for setpoint and readback rows; pause,
    manual activity, diagnostic notes and HTML reports can add more.
    This is advisory only and must never change the instrument workflow.
    """
    try:
        values = (duration_s, interval_s, readback_interval_s)
        if not all(math.isfinite(float(v)) for v in values):
            return None
        duration, interval, readback_interval = map(float, values)
        if duration < 0 or interval <= 0 or readback_interval <= 0:
            return None
        if not isinstance(channel_count, int) or channel_count < 1:
            return None
        disk = disk_usage(Path(output_path).parent)
        if disk.free < 0:
            return None
        estimated_events = channel_count * (
            math.ceil(duration / interval) + math.ceil(duration / readback_interval) + 2
        )
        estimated = estimated_events * BYTES_PER_EVENT
        threshold = estimated + RESERVE_BYTES
        if disk.free >= threshold:
            return None
        def gib(n):
            return f'{n / (1024 ** 3):.2f} GiB'
        return ('[STORAGE WARNING] Estimated measurement CSV budget '
                f'{gib(estimated)}, available {gib(disk.free)} on output filesystem; '
                f'recommended free capacity including reserve {gib(threshold)}. '
                'This is a rough estimate, not an allocation; extra events, '
                'HTML reports and other processes can consume more space. '
                'The run is not blocked by this advisory.')
    except (OSError, ValueError, TypeError, OverflowError):
        return None
