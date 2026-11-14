"""Shared workforce/time helpers used by services and the scheduler."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.models.enums import DayType

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def combine(day: date, clock: time) -> datetime:
    return datetime.combine(day, clock)


def shift_window(shift_date: date, start: time, end: time, crosses_midnight: bool) -> tuple[datetime, datetime]:
    start_dt = combine(shift_date, start)
    end_day = shift_date + timedelta(days=1) if crosses_midnight else shift_date
    end_dt = combine(end_day, end)
    return start_dt, end_dt


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def rest_gap_hours(previous_end: datetime, next_start: datetime) -> float:
    return (next_start - previous_end).total_seconds() / 3600.0


def hours_between(start: datetime, end: datetime) -> float:
    return max(0.0, (end - start).total_seconds() / 3600.0)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_bounds(day: date) -> tuple[date, date]:
    monday = week_start(day)
    return monday, monday + timedelta(days=6)


def date_range(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def classify_day(day: date, holiday_dates: set[date] | None = None) -> DayType:
    if holiday_dates and day in holiday_dates:
        return DayType.HOLIDAY
    if day.weekday() >= 5:
        return DayType.WEEKEND
    return DayType.WEEKDAY


def preference_for_code(code: str) -> str:
    return {"A": "MORNING", "B": "EVENING", "C": "NIGHT"}.get(code, "NONE")


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))
