"""Date and duration parsing utilities for industrial spreadsheets.

Industrial telemetry spreadsheets frequently mix standard timestamps (ISO/wall-clock)
with duration/elapsed time counters (e.g. running hours, stage durations).
Standard datetime parsing often misinterprets durations (e.g. 36:15:00) as
wrapped clock times or invalid dates. This module distinguishes date formats from
duration formats and converts duration serial numbers to total seconds.
"""

from __future__ import annotations

import datetime
import re
from typing import Any

# Regular expression matching Excel elapsed duration formats such as:
# [h]:mm:ss, [hh]:mm:ss, [m]:ss, [mm]:ss, [s], [ss], [h]:mm
DURATION_FORMAT_REGEX = re.compile(r"\[([hms]{1,2})\]", re.IGNORECASE)

# Standard Excel base epochs
# 1900 system: 1899-12-30 (due to Excel's intentional 1900 leap year bug)
EXCEL_1900_EPOCH = datetime.datetime(1899, 12, 30)
# 1904 system: 1904-01-01
EXCEL_1904_EPOCH = datetime.datetime(1904, 1, 1)

SECONDS_PER_DAY = 86400.0


def is_duration_format(number_format: str | None) -> bool:
    """Return True if the Excel number format string denotes an elapsed duration.

    Elapsed durations in Excel use bracket notation, e.g. [h]:mm:ss or [m]:ss.
    """
    if not number_format:
        return False
    return bool(DURATION_FORMAT_REGEX.search(number_format))


def parse_duration_to_seconds(
    value: Any,
    number_format: str | None = None,
) -> float | None:
    """Convert an Excel duration value to total elapsed seconds.

    If value is numeric (int or float) representing Excel day-fractions:
    1.0 = 24 hours = 86400 seconds.

    If value is a string representation such as '36:15:00' or '120:00':
    Parses hours, minutes, seconds directly to total seconds.

    Returns None if the value cannot be parsed as a duration.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        # Excel stores elapsed time as fractions of a day (1 day = 86400 s)
        return round(float(value) * SECONDS_PER_DAY, 6)

    if isinstance(value, datetime.timedelta):
        return value.total_seconds()

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None

        # Check for HH:MM:SS or HHH:MM:SS format
        parts = cleaned.split(":")
        if len(parts) == 3:
            try:
                hours = float(parts[0])
                minutes = float(parts[1])
                seconds = float(parts[2])
                return round(hours * 3600.0 + minutes * 60.0 + seconds, 6)
            except ValueError:
                return None
        elif len(parts) == 2:
            try:
                minutes = float(parts[0])
                seconds = float(parts[1])
                return round(minutes * 60.0 + seconds, 6)
            except ValueError:
                return None

        # Try plain float string
        try:
            return round(float(cleaned) * SECONDS_PER_DAY, 6)
        except ValueError:
            return None

    return None


def parse_excel_date(
    value: Any,
    date_epoch: str = "1900",
) -> datetime.datetime | datetime.date | datetime.time | None:
    """Convert an Excel serial date number or date object to Python datetime.

    Handles both 1900 and 1904 date epochs.
    """
    if value is None:
        return None

    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value

    if isinstance(value, (int, float)):
        epoch = EXCEL_1904_EPOCH if date_epoch == "1904" else EXCEL_1900_EPOCH
        days = float(value)
        # Excel 1900 leap year bug: day 60 is Feb 29 1900 (does not exist).
        # Openpyxl and Excel handle days < 60 and >= 61.
        # If using standard 1899-12-30 epoch:
        # Day 1 -> 1899-12-31 (Excel says 1900-01-01)
        # Day 60 -> 1900-02-28 + 1 -> 1900-02-29 (bug)
        # Day 61 -> 1900-03-01
        if date_epoch == "1900":
            if days < 60:
                epoch = datetime.datetime(1899, 12, 31)
            else:
                epoch = datetime.datetime(1899, 12, 30)

        delta = datetime.timedelta(days=days)
        return epoch + delta

    if isinstance(value, str):
        cleaned = value.strip()
        # Try parsing ISO 8601
        try:
            return datetime.datetime.fromisoformat(cleaned)
        except ValueError:
            pass

    return None
