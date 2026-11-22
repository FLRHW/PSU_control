"""Conservative display-only CV/CC inference from existing measurements.

Not an instrument mode readback and NOT a replacement for a PSU LSR event.
This module is intentionally pure: no SCPI, socket or I/O operations.
"""


def estimate_regulation(voltage_set, current_limit, output_enabled,
                        measured_voltage, measured_current):
    """Return 'CV likely', 'CC likely' or None.

    Avoid a confident label at zero voltage/current, while output state is
    unknown, or where measured current/voltage contradict programmed limits.
    """
    try:
        import math
        vset, ilim, vm, im = map(float, (
            voltage_set, current_limit, measured_voltage, measured_current))
        if not all(math.isfinite(v) for v in (vset, ilim, vm, im)):
            return None
        if output_enabled is not True or vset < 0.2 or ilim < 0.02:
            return None
        if vm < -0.15 or im < -0.02:
            return None
        # Do not present impossible/settling measurements as a regulation mode.
        if im > ilim * 1.25 + 0.03 or vm > vset * 1.25 + 0.15:
            return None
        voltage_close = abs(vm - vset) <= max(0.12, 0.05 * vset)
        current_near_limit = im >= 0.88 * ilim
        voltage_low = vm < vset - max(0.15, 0.10 * vset)
        if current_near_limit and voltage_low:
            return 'CC likely'
        if voltage_close and im < 0.95 * ilim:
            return 'CV likely'
    except (ValueError, TypeError, OverflowError):
        return None
    return None
