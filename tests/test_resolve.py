from datetime import datetime, timedelta, timezone

import pytest

from pollparse.resolve import (
    WARNING_DEADLINE_FAR_FUTURE,
    WARNING_DEADLINE_IN_PAST,
    WARNING_INVALID_DATE,
    resolve,
)

TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 8, 28, 14, 0, tzinfo=TZ)  # 2pm Fri


def at(month, day, hour, minute=0, second=0):
    return datetime(2026, month, day, hour, minute, second, tzinfo=TZ)


def absolute(**kwargs):
    base = {
        "kind": "absolute",
        "day_offset": None,
        "hour": None,
        "minute": None,
        "meridiem": None,
        "hour_is_24h": False,
    }
    base.update(kwargs)
    return base


def test_reject_now_without_timezone():
    with pytest.raises(ValueError):
        naive = datetime(2026, 8, 28, 14, 0)  # noqa: DTZ001
        resolve(absolute(hour=9, minute=0), naive)


def test_reject_known_kind():
    with pytest.raises(ValueError):
        resolve({"kind": "not_a_kind"}, NOW)


def test_get_nearest_9pm_when_not_specified():
    got = resolve(absolute(hour=9, minute=0), NOW)
    assert got["at"] == at(8, 28, 21, 0)
    assert got["warnings"] == []


def test_set_specific_time_when_specified():
    got = resolve(absolute(hour=9, minute=0, meridiem="am", hour_is_24h=True), NOW)
    assert got["at"] == at(8, 29, 9, 0)


def test_both_12hr_possible_when_not_specified():
    got = resolve(absolute(hour=12, minute=0), NOW)
    assert got["at"] == at(8, 29, 0, 0)


def test_warn_user_when_deadline_passed():
    got = resolve(
        absolute(day_offset=0, hour=8, minute=0, meridiem="am", hour_is_24h=True), NOW
    )
    assert got["at"] == at(8, 28, 8, 0)
    assert WARNING_DEADLINE_IN_PAST in got["warnings"]


def test_deadline_tomorrow_when_today_time_passed():
    got = resolve(absolute(hour=8, minute=0, meridiem="am", hour_is_24h=True), NOW)
    assert got["at"] == at(8, 29, 8, 0)
    assert got["warnings"] == []


def test_only_day_means_EOD():
    got = resolve(absolute(day_offset=1), NOW)
    assert got["at"] == at(8, 29, 23, 59, 59)


def test_evening_means_EOD():
    got = resolve(absolute(part="晚上"), NOW)
    assert got["at"] == at(8, 28, 23, 59, 59)


def test_noon_means_nearest_noon():
    got = resolve(absolute(part="中午"), NOW)
    assert got["at"] == at(8, 29, 12, 0)


def test_tomorrow_noon():
    got = resolve(absolute(day_offset=1, part="中午"), NOW)
    assert got["at"] == at(8, 29, 12, 0)


def test_if_specified_day_is_today_means_EOD():
    got = resolve(
        {
            "kind": "weekday",
            "weekday": 5,
            "week_offset": None,
            "hour": None,
            "minute": None,
            "meridiem": None,
            "hour_is_24h": False,
        },
        NOW,
    )
    assert got["at"] == at(8, 28, 23, 59, 59)


def test_move_to_next_week_if_time_passed():
    got = resolve(
        {
            "kind": "weekday",
            "weekday": 5,
            "week_offset": None,
            "hour": None,
            "minute": None,
            "meridiem": None,
            "hour_is_24h": False,
            "part": "中午",
        },
        NOW,
    )
    assert got["at"] == at(9, 4, 12, 0)


def test_remind_faraway_date():
    got = resolve(
        {
            "kind": "date",
            "month": 3,
            "day": 15,
            "year": None,
            "hour": None,
            "minute": None,
            "meridiem": None,
            "hour_is_24h": False,
        },
        NOW,
    )
    assert got["at"].year == 2027
    assert got["at"].month == 3 and got["at"].day == 15
    assert WARNING_DEADLINE_FAR_FUTURE in got["warnings"]


def test_warn_on_invalid_date_not_crash():
    got = resolve(
        {
            "kind": "date",
            "month": 2,
            "day": 30,
            "year": None,
            "hour": None,
            "minute": None,
            "meridiem": None,
            "hour_is_24h": False,
        },
        NOW,
    )
    assert WARNING_INVALID_DATE in got["warnings"]
    assert got["at"] is not None


def test_relative_time_add_from_now():
    got = resolve({"kind": "relative", "seconds": 3600}, NOW)
    assert got["at"] == at(8, 28, 15, 0)
    assert got["warnings"] == []


def test_remind_faraway_date_on_relative():
    got = resolve({"kind": "relative", "seconds": 60 * 60 * 24 * 40}, NOW)
    assert WARNING_DEADLINE_FAR_FUTURE in got["warnings"]


def month_end(**kwargs):
    base = {
        "kind": "month_end",
        "month_offset": 0,
        "hour": None,
        "minute": None,
        "meridiem": None,
        "hour_is_24h": False,
    }
    return {**base, **kwargs}


def test_month_end_is_last_day_of_this_month():
    assert resolve(month_end(), NOW)["at"] == at(8, 31, 23, 59, 59)


def test_month_end_next_month():
    assert resolve(month_end(month_offset=1), NOW)["at"] == at(9, 30, 23, 59, 59)


def test_month_end_handles_february_length():
    leap = datetime(2028, 2, 3, 9, 0, tzinfo=TZ)
    assert resolve(month_end(), leap)["at"] == datetime(
        2028, 2, 29, 23, 59, 59, tzinfo=TZ
    )


def test_month_end_rolls_over_the_year():
    december = datetime(2026, 12, 5, 9, 0, tzinfo=TZ)
    assert resolve(month_end(month_offset=1), december)["at"] == datetime(
        2027, 1, 31, 23, 59, 59, tzinfo=TZ
    )


def test_month_end_on_the_last_day_after_the_deadline_moves_to_next_month():
    # 8/31 23:59:59 之後才問「月底截止」—— 這個月底已經過了，指的是下個月底
    late = datetime(2026, 8, 31, 23, 59, 59, tzinfo=TZ)
    assert resolve(month_end(), late)["at"] == at(9, 30, 23, 59, 59)


def test_unknown_kind_still_raises():
    with pytest.raises(ValueError):
        resolve({"kind": "lunar_new_year"}, NOW)


def date_deadline(month, day, **kwargs):
    base = {
        "kind": "date",
        "month": month,
        "day": day,
        "year": None,
        "hour": None,
        "minute": None,
        "meridiem": None,
        "hour_is_24h": False,
    }
    return {**base, **kwargs}


def test_feb_29_resolves_into_next_leap_year_without_warning():
    now = datetime(2027, 1, 10, 9, 0, tzinfo=TZ)
    got = resolve(date_deadline(2, 29), now)
    assert got["at"] == datetime(2028, 2, 29, 23, 59, 59, tzinfo=TZ)
    assert WARNING_INVALID_DATE not in got["warnings"]


def test_feb_29_in_a_leap_year_does_not_warn_about_next_year():
    now = datetime(2028, 1, 10, 9, 0, tzinfo=TZ)
    got = resolve(date_deadline(2, 29), now)
    assert got["at"] == datetime(2028, 2, 29, 23, 59, 59, tzinfo=TZ)
    assert WARNING_INVALID_DATE not in got["warnings"]


def test_feb_29_warns_when_neither_candidate_year_is_a_leap_year():
    now = datetime(2026, 1, 10, 9, 0, tzinfo=TZ)
    got = resolve(date_deadline(2, 29), now)
    assert got["warnings"].count(WARNING_INVALID_DATE) == 1


def test_invalid_date_warns_exactly_once():
    got = resolve(date_deadline(2, 30), NOW)
    assert got["warnings"].count(WARNING_INVALID_DATE) == 1
