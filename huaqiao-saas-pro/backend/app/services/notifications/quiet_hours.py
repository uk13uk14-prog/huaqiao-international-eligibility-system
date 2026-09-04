"""Quiet hours — defer non-CRITICAL; CRITICAL may break through."""
from __future__ import annotations
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from .constants import DEFAULT_QUIET_END, DEFAULT_QUIET_START, DEFAULT_TIMEZONE, PRIORITY_CRITICAL

def _parse_hhmm(value: str, fallback: str) -> time:
    raw = (value or fallback).strip()
    try:
        hh, mm = raw.split(":")[:2]
        return time(int(hh), int(mm))
    except Exception:
        fh, fm = fallback.split(":")
        return time(int(fh), int(fm))

def in_quiet_hours(when: datetime | None = None, *, quiet_start: str = DEFAULT_QUIET_START,
                   quiet_end: str = DEFAULT_QUIET_END, timezone: str = DEFAULT_TIMEZONE) -> bool:
    try:
        tz = ZoneInfo(timezone or DEFAULT_TIMEZONE)
    except Exception:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    now = when or datetime.utcnow()
    local = (now.replace(tzinfo=ZoneInfo("UTC")) if now.tzinfo is None else now).astimezone(tz)
    start = _parse_hhmm(quiet_start, DEFAULT_QUIET_START)
    end = _parse_hhmm(quiet_end, DEFAULT_QUIET_END)
    t = local.timetz().replace(tzinfo=None)
    if start <= end:
        return start <= t < end
    return t >= start or t < end

def next_quiet_end(when: datetime | None = None, *, quiet_start: str = DEFAULT_QUIET_START,
                   quiet_end: str = DEFAULT_QUIET_END, timezone: str = DEFAULT_TIMEZONE) -> datetime:
    try:
        tz = ZoneInfo(timezone or DEFAULT_TIMEZONE)
    except Exception:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    now = when or datetime.utcnow()
    local = (now.replace(tzinfo=ZoneInfo("UTC")) if now.tzinfo is None else now).astimezone(tz)
    end = _parse_hhmm(quiet_end, DEFAULT_QUIET_END)
    candidate = local.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if candidate <= local:
        candidate = candidate + timedelta(days=1)
    return candidate.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

def should_defer_send(priority: str, prefs) -> bool:
    if (priority or "").upper() == PRIORITY_CRITICAL:
        return False
    start = getattr(prefs, "quiet_hours_start", None) or DEFAULT_QUIET_START
    end = getattr(prefs, "quiet_hours_end", None) or DEFAULT_QUIET_END
    tz = getattr(prefs, "timezone", None) or DEFAULT_TIMEZONE
    return in_quiet_hours(quiet_start=start, quiet_end=end, timezone=tz)
