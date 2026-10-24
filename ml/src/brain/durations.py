"""Lightweight spoken-duration parsing."""

import re


_UNITS = {"second": 1, "seconds": 1, "sec": 1, "secs": 1,
          "minute": 60, "minutes": 60, "min": 60, "mins": 60,
          "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600}


def parse_duration(text: str) -> int | None:
    """Spoken duration -> seconds. 'ten minutes', '90 seconds',
    '1 hour 30 minutes', 'an hour and a half', 'one hour twenty five minutes'."""
    from . import calc
    t = calc.normalize(text.lower().strip())[0].replace("-", " ")
    m = re.search(r"half an? (hour|minute|second)s?", t)
    if m and not re.search(r"\d", t):
        return int(0.5 * _UNITS[m.group(1)])
    total, found = 0.0, False
    for m in re.finditer(
            r"(\d+(?:\.\d+)?|an?)\s*(and a half\s+)?"
            r"(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b(\s+and a half)?",
            t):
        num = 1.0 if m.group(1) in ("a", "an") else float(m.group(1))
        if m.group(2) or m.group(4):
            num += 0.5
        total += num * _UNITS[m.group(3)]
        found = True
    return int(total) if found else None
