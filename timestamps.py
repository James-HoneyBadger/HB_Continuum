# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Normalize archived date strings into sortable timestamps.

Archive timestamps are stored as the original text (which must be preserved
verbatim) plus a normalized epoch value and a precision marker. Unknown and
unparseable dates stay explicitly unknown rather than being guessed, so a
timeline can place them deterministically without inventing chronology.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

def _epoch(value):
    """Epoch seconds for a datetime, treating naive values as UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    try:
        return int(value.timestamp())
    except (OverflowError, OSError, ValueError):
        return None

def _precision(text):
    """`second` when the text carries a time of day, else `day`."""
    return 'second' if ':' in text else 'day'

def parse_timestamp(value):
    """Return `(epoch_seconds, precision)` for an archived date string.

    Supports RFC 2822 mail dates and ISO 8601 timestamps. Returns
    `(None, None)` for empty, ambiguous or unparseable input.
    """
    if not isinstance(value, str) or not value.strip():
        return None, None
    text = value.strip()
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError):
        parsed = None
    if parsed is not None:
        epoch = _epoch(parsed)
        return (epoch, _precision(text)) if epoch is not None else (None, None)
    iso = text[:-1] + '+00:00' if text.endswith(('Z', 'z')) else text
    try:
        parsed = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None, None
    epoch = _epoch(parsed)
    return (epoch, _precision(text)) if epoch is not None else (None, None)
