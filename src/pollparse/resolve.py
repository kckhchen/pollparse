from datetime import date, datetime, time, timedelta

from . import time_lexicon

__all__ = [
    "WARNING_DEADLINE_FAR_FUTURE",
    "WARNING_DEADLINE_IN_PAST",
    "WARNING_INVALID_DATE",
    "resolve",
]

WARNING_DEADLINE_IN_PAST = "deadline_in_past"
WARNING_DEADLINE_FAR_FUTURE = "deadline_far_future"
WARNING_INVALID_DATE = "invalid_date"

_SUSPICIOUS_SPAN = timedelta(days=30)
_END_OF_DAY = time(23, 59, 59)


def _moments(deadline: dict) -> list[time]:
    if deadline["hour"] is None:
        end_of_part = time_lexicon.PART_END.get(deadline.get("part"))
        return [time(*end_of_part)] if end_of_part else [_END_OF_DAY]
    return _hour_options(deadline)


def _hour_options(deadline: dict) -> list[time]:
    hour, minute = deadline["hour"], deadline["minute"]
    if deadline["hour_is_24h"] or hour > 12:
        return [time(hour % 24, minute)]
    if hour == 12:
        return [time(0, minute), time(12, minute)]
    return [time(hour, minute), time(hour + 12, minute)]


def _at(day: date, moment: time, now: datetime) -> datetime:
    return datetime.combine(day, moment, tzinfo=now.tzinfo)


def _earliest_future(
    days: list[date], moments: list[time], now: datetime
) -> datetime | None:
    future = sorted(
        candidate
        for day in days
        for moment in moments
        if (candidate := _at(day, moment, now)) > now
    )
    return future[0] if future else None


def _relative_to_today(
    moments: list[time], day_offset: int | None, now: datetime, warnings: list[str]
) -> datetime:
    """把「今天／明天／沒講哪天」加上一組候選時刻，解成最早的未來時間。"""
    if day_offset is None:
        resolved = _earliest_future(
            [now.date(), now.date() + timedelta(days=1)], moments, now
        )
        return (
            resolved
            if resolved
            else _at(now.date() + timedelta(days=1), moments[0], now)
        )

    day = now.date() + timedelta(days=day_offset)
    resolved = _earliest_future([day], moments, now)
    if resolved is None:
        warnings.append(WARNING_DEADLINE_IN_PAST)
        resolved = _at(day, moments[-1], now)
    return resolved


def _resolve_absolute(deadline: dict, now: datetime, warnings: list[str]) -> datetime:
    return _relative_to_today(_moments(deadline), deadline["day_offset"], now, warnings)


def _resolve_date(deadline: dict, now: datetime, warnings: list[str]) -> datetime:
    moments = _moments(deadline)
    years = [deadline["year"]] if deadline["year"] else [now.year, now.year + 1]
    days = []
    for year in years:
        try:
            days.append(date(year, deadline["month"], deadline["day"]))
        except ValueError:
            warnings.append(WARNING_INVALID_DATE)
    if not days:
        return _at(now.date(), _END_OF_DAY, now)

    resolved = _earliest_future(days, moments, now)
    if resolved is None:
        warnings.append(WARNING_DEADLINE_IN_PAST)
        resolved = _at(days[-1], moments[-1], now)
    return resolved


def _resolve_weekday(deadline: dict, now: datetime, warnings: list[str]) -> datetime:
    moments = _moments(deadline)
    this_week = now.date() + timedelta(days=deadline["weekday"] - now.isoweekday())
    week_offset = deadline["week_offset"]

    if week_offset is None:
        resolved = _earliest_future(
            [this_week, this_week + timedelta(days=7)], moments, now
        )
        return (
            resolved
            if resolved
            else _at(this_week + timedelta(days=7), moments[-1], now)
        )

    day = this_week + timedelta(days=7 * week_offset)
    resolved = _earliest_future([day], moments, now)
    if resolved is None:
        warnings.append(WARNING_DEADLINE_IN_PAST)
        resolved = _at(day, moments[-1], now)
    return resolved


def resolve(deadline: dict, now: datetime) -> dict:
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise ValueError(
            "now must be timezone-aware; a naive datetime makes the result "
            "drift with the deployment environment"
        )

    warnings: list[str] = []
    kind = deadline["kind"]
    if kind == "relative":
        at = now + timedelta(seconds=deadline["seconds"])
    elif kind == "absolute":
        at = _resolve_absolute(deadline, now, warnings)
    elif kind == "date":
        at = _resolve_date(deadline, now, warnings)
    elif kind == "weekday":
        at = _resolve_weekday(deadline, now, warnings)
    else:
        raise ValueError(f"unknown deadline kind: {kind!r}")

    if at - now > _SUSPICIOUS_SPAN:
        warnings.append(WARNING_DEADLINE_FAR_FUTURE)
    return {"at": at, "warnings": warnings}
