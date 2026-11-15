"""CPX400DP regulation-mode event decoding.

LSR<N>? is a READ-AND-CLEAR event register, not a continuously readable
mode register. Display only the last unambiguous observed mode transition,
never claim it is guaranteed current state.
CPX400DP Instruction Manual, 'Limit Event Status' section:
bit 0 entered CV, bit 1 entered CC, bit 4 entered power-limit UNREG.
"""
import re


def decode_limit_event(response, enabled, previous=None):
    """Return 'CV', 'CC', 'UNREG', or None (unknown).

    If no new transition event is reported, retain the last observed mode
    only while the output remains enabled. Conflicting simultaneous events
    are unknown: their chronological order cannot be reconstructed.
    """
    if not enabled:
        return None
    if isinstance(response, str):
        value = response.strip()
        if not re.fullmatch(r'(?:0[xX][0-9a-fA-F]+|[0-9]+)', value):
            raise ValueError('Invalid CPX400DP LSR response')
        mask = int(value, 0) if value.lower().startswith('0x') else int(value)
    elif isinstance(response, int):
        mask = response
    else:
        raise ValueError('Invalid CPX400DP LSR response')
    if mask < 0 or mask > 255:
        raise ValueError('Invalid CPX400DP LSR value')
    # Trips/protection demand a separate fault indication; never call them CV.
    if mask & (0x40 | 0x08 | 0x04):
        return None
    flags = [name for bit, name in ((0x10,'UNREG'),(0x02,'CC'),(0x01,'CV')) if mask & bit]
    if len(flags) > 1:
        return None
    if flags:
        return flags[0]
    return previous if previous in ('CV','CC','UNREG') else None
