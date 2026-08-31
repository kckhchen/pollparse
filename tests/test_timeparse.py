# "now" means 2026-08-28 FRI 14:00 +08:00。

from datetime import datetime, timedelta, timezone

import pytest

from pollparse.baseline.timeparse import parse_one
from pollparse.resolve import resolve

TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 8, 28, 14, 0, tzinfo=TZ)


def when(text):
    deadline = parse_one(text)
    return None if deadline is None else resolve(deadline, NOW)["at"]


def at(month, day, hour, minute=0, second=0):
    return datetime(2026, month, day, hour, minute, second, tzinfo=TZ)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("晚上十二點截止", at(8, 29, 0, 0)),
        ("晚間十二點截止", at(8, 29, 0, 0)),
        ("午夜十二點截止", at(8, 29, 0, 0)),
        ("半夜十二點截止", at(8, 29, 0, 0)),
        ("凌晨十二點截止", at(8, 29, 0, 0)),
        ("早上十二點截止", at(8, 29, 0, 0)),
        ("中午十二點截止", at(8, 29, 12, 0)),
        ("下午十二點截止", at(8, 29, 12, 0)),
    ],
)
def test_12_oclock_meanings_correct(text, expected):
    assert when(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("晚上三點截止", at(8, 29, 3, 0)),
        ("晚上四點截止", at(8, 29, 4, 0)),
        ("晚上五點截止", at(8, 28, 17, 0)),
        ("晚上七點截止", at(8, 28, 19, 0)),
        ("下午一點截止", at(8, 29, 13, 0)),
    ],
)
def test_what_counts_as_evening(text, expected):
    assert when(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("早上截止", at(8, 29, 12, 0)),
        ("中午截止", at(8, 29, 12, 0)),
        ("晚上截止", at(8, 28, 23, 59, 59)),
        ("半夜截止", at(8, 28, 23, 59, 59)),
        ("明天截止", at(8, 29, 23, 59, 59)),
        ("後天截止", at(8, 30, 23, 59, 59)),
        ("明天中午截止", at(8, 29, 12, 0)),
        ("今天晚上截止", at(8, 28, 23, 59, 59)),
        ("中午前", at(8, 29, 12, 0)),
    ],
)
def test_pin_to_end_of_period(text, expected):
    assert when(text) == expected


def test_weekday_plus_period():
    assert when("週五中午截止") == at(9, 4, 12, 0)
    assert when("週四晚上截止") == at(9, 3, 23, 59, 59)


def test_date_plus_period():
    assert when("3/15晚上截止").month == 3


@pytest.mark.parametrize(
    "text",
    ["3/15之前截止", "週五之前截止", "明天10:00之前截止", "明天之前收單"],
)
def test_endwords_should_not_be_separated(text):
    assert when(text) is not None


def test_停止_is_not_endword():
    assert when("九點停止投票") is None
    assert when("九點截止投票") is not None


def test_投完_is_endword():
    assert when("今天下午三點前投完") == at(8, 28, 15, 0)


def test_reject_invalid_time():
    assert parse_one("週五99點截止") is None


def test_period_without_endword_is_not_time():
    assert parse_one("晚上") is None
    assert parse_one("明天") is None


def test_relative_time():
    assert when("限時兩小時") == at(8, 28, 16, 0)
    assert when("十分鐘後截止") == at(8, 28, 14, 10)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("今晚截止", at(8, 28, 23, 59, 59)),
        ("今晚十一點截止", at(8, 28, 23, 0)),
        ("今晚8點收單", at(8, 28, 20, 0)),
        ("明早八點截止", at(8, 29, 8, 0)),
        ("明晚截止", at(8, 29, 23, 59, 59)),
        ("三天後截止", at(8, 31, 23, 59, 59)),
        ("3天後截止", at(8, 31, 23, 59, 59)),
        ("過三天截止", at(8, 31, 23, 59, 59)),
        ("再兩天截止", at(8, 30, 23, 59, 59)),
        ("月底截止", at(8, 31, 23, 59, 59)),
        ("月底前", at(8, 31, 23, 59, 59)),
        ("本月底截止", at(8, 31, 23, 59, 59)),
        ("下個月底截止", at(9, 30, 23, 59, 59)),
        ("週末截止", at(8, 30, 23, 59, 59)),
        ("週末前", at(8, 30, 23, 59, 59)),
        ("下週末截止", at(9, 6, 23, 59, 59)),
        ("今天內", at(8, 28, 23, 59, 59)),
        ("明天內截止", at(8, 29, 23, 59, 59)),
    ],
)
def test_gap_forms(text, expected):
    assert when(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "出發前",
        "生日前一天截止",
        "吃飯前給我答案",
        "放學前截止",
        "下班前截止",
        "三點",
        "八點",
    ],
)
def test_unresolvable_stays_unresolvable(text):
    assert parse_one(text) is None
