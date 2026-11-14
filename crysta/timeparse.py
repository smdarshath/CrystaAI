"""Tiny reminder-time parser: 'in 10 minutes', 'in 2 hours', 'at 5pm', 'tomorrow at 9:30'."""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

UNITS = {"second": 1, "sec": 1, "minute": 60, "min": 60, "hour": 3600, "hr": 3600, "day": 86400}


def parse_due(text, now=None):
    """Return (title_without_time_phrase, due_epoch or None)."""
    now_dt = datetime.fromtimestamp(now or time.time())
    m = re.search(r"\bin\s+(\d+|an?|half an)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)\b", text, re.I)
    if m:
        qty = {"a": 1, "an": 1, "half an": 0.5}.get(m.group(1).lower(), None)
        qty = float(m.group(1)) if qty is None else qty
        unit = UNITS[m.group(2).lower().rstrip("s")]
        due = (now_dt + timedelta(seconds=qty * unit)).timestamp()
        return _clean(text, m), due
    m = re.search(r"\b(tomorrow\s+)?at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text, re.I)
    if m:
        h, mi, ap = int(m.group(2)), int(m.group(3) or 0), (m.group(4) or "").lower()
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        if h > 23 or mi > 59:
            return text.strip(), None
        due_dt = now_dt.replace(hour=h, minute=mi, second=0, microsecond=0)
        if m.group(1):
            due_dt += timedelta(days=1)
        elif due_dt <= now_dt:
            due_dt += timedelta(days=1)
        return _clean(text, m), due_dt.timestamp()
    return text.strip(), None


def _clean(text, m):
    return re.sub(r"\s+", " ", (text[:m.start()] + " " + text[m.end():])).strip(" ,.")
