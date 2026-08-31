import re

from .. import time_lexicon
from ..numerals import to_int
from ._regex import alternation

__all__ = ["find_candidates", "parse_one"]

_DAY = alternation(time_lexicon.DAY_OFFSET)
_PART = alternation(time_lexicon.PART_KIND)
_END = rf"(?!投完[才就可])(?:{alternation(time_lexicon.END_MARKERS)})"
_BEFORE = alternation(time_lexicon.BEFORE_MARKERS)
_WITHIN = alternation(time_lexicon.WITHIN_MARKERS)
_LEAD = alternation(time_lexicon.LEAD_VERBS)
_UNIT = alternation(time_lexicon.SECONDS_PER_UNIT)
_WEEKDAY = "".join(char for char, _ in time_lexicon.WEEKDAY_CHARS)
_WEEK_PREFIX = alternation(time_lexicon.WEEK_PREFIX)

_NUM = r"\d{1,4}|[零一二兩三四五六七八九十百千]{1,5}"

_CLOCK = (
    rf"(?:(?P<day>{_DAY}))?(?:(?P<part>{_PART}))?"
    rf"(?P<hour>{_NUM})點(?P<minute>半|整|(?:{_NUM})分)?"
)
_CLOCK_CORE = rf"(?P<hour>{_NUM})點(?P<minute>半|整|(?:{_NUM})分)?"
_CLOCK_NO_DAY = rf"(?:(?P<part>{_PART}))?(?:{_CLOCK_CORE})?"

_MONTH = r"1[0-2]|0?[1-9]"
_DAY_NUM = r"3[01]|[12]\d|0?[1-9]"
_DATE_NUM = r"\d{1,2}|[零一二三四五六七八九十]{1,3}"
_DATE = (
    rf"(?:(?P<month>{_MONTH})/(?P<day_num>{_DAY_NUM})"
    rf"|(?P<month2>{_DATE_NUM})月(?P<day_num2>{_DATE_NUM})[日號]?)"
)
_WEEK = rf"(?P<week_prefix>{_WEEK_PREFIX})?(?:週|星期|禮拜)(?P<weekday>[{_WEEKDAY}])"
_DAYPART = alternation(time_lexicon.DAYPART_OF)
_MONTH_END = alternation(time_lexicon.MONTH_END_WORDS)
_WEEKEND = alternation(time_lexicon.WEEKEND_WORDS)


_Groups = dict[str, str | None]


def _read_clock(groups: _Groups) -> dict | None:
    hour_text = groups.get("hour")
    if hour_text is None:
        return None
    hour = to_int(hour_text)
    if hour is None or hour > 24:
        return None

    minute_text = groups.get("minute")
    if minute_text is None:
        minute = 0
    elif minute_text == "半":
        minute = 30
    elif minute_text == "整":
        minute = 0
    else:
        minute = to_int(minute_text[:-1])
        if minute is None or minute > 59:
            return None

    part = groups.get("part")
    meridiem = time_lexicon.meridiem_of(part)
    return {
        "hour": time_lexicon.to_24_hour(hour, part) if meridiem else hour,
        "minute": minute,
        "meridiem": meridiem,
        "hour_is_24h": meridiem is not None,
    }


def _handle_relative(groups: _Groups) -> dict | None:
    unit = groups.get("unit")
    amount_text = groups.get("amount")
    if unit is None or amount_text is None:
        return None
    seconds_per_unit = time_lexicon.SECONDS_PER_UNIT[unit]
    if amount_text == "半":
        amount = 0.5
    else:
        amount = to_int(amount_text)
        if amount is None:
            return None
    return {"kind": "relative", "seconds": int(amount * seconds_per_unit)}


def _handle_absolute(groups: _Groups) -> dict | None:
    clock = _read_clock(groups)
    if clock is None:
        return None
    day_word = groups.get("day")
    return {
        "kind": "absolute",
        "day_offset": time_lexicon.DAY_OFFSET[day_word] if day_word else None,
        **clock,
    }


def _handle_no_clock(groups: _Groups) -> dict | None:
    day_word, part = groups.get("day"), groups.get("part")
    if day_word is None and part is None:
        return None
    deadline = {
        "kind": "absolute",
        "day_offset": time_lexicon.DAY_OFFSET[day_word] if day_word else None,
        "hour": None,
        "minute": None,
        "meridiem": None,
        "hour_is_24h": False,
    }
    if part is not None:
        deadline["part"] = part
    return deadline


def _handle_daypart(groups: _Groups) -> dict | None:
    word = groups.get("daypart")
    if word is None:
        return None
    day_offset, part = time_lexicon.DAYPART_OF[word]
    deadline = {
        "kind": "absolute",
        "day_offset": day_offset,
        "hour": None,
        "minute": None,
        "meridiem": None,
        "hour_is_24h": False,
    }
    # 帶鐘點時（「今晚十一點截止」）要用展開出來的時段做 12/24 換算，
    # 所以把 part 塞回 groups 再交給共用的那條路。
    return (
        deadline if _apply_clock_or_part(deadline, {**groups, "part": part}) else None
    )


def _handle_days_later(groups: _Groups) -> dict | None:
    amount_text = groups.get("days")
    if amount_text is None:
        return None
    days = to_int(amount_text)
    if days is None or not 1 <= days <= 365:
        return None
    deadline = {
        "kind": "absolute",
        "day_offset": days,
        "hour": None,
        "minute": None,
        "meridiem": None,
        "hour_is_24h": False,
    }
    return deadline if _apply_clock_or_part(deadline, groups) else None


def _handle_month_end(groups: _Groups) -> dict | None:
    word = groups.get("month_end")
    if word is None:
        return None
    deadline = {
        "kind": "month_end",
        "month_offset": time_lexicon.MONTH_END_WORDS[word],
        "hour": None,
        "minute": None,
        "meridiem": None,
        "hour_is_24h": False,
    }
    return deadline if _apply_clock_or_part(deadline, groups) else None


def _handle_weekend(groups: _Groups) -> dict | None:
    word = groups.get("weekend")
    if word is None:
        return None
    deadline = {
        "kind": "weekday",
        "weekday": 7,
        "week_offset": 1 if word.startswith("下") else None,
        "hour": None,
        "minute": None,
        "meridiem": None,
        "hour_is_24h": False,
    }
    return deadline if _apply_clock_or_part(deadline, groups) else None


def _handle_clock24(groups: _Groups) -> dict | None:
    hour_text, minute_text = groups.get("h24"), groups.get("m24")
    if hour_text is None or minute_text is None:
        return None
    hour, minute = int(hour_text), int(minute_text)
    if hour > 23 or minute > 59:
        return None
    day_word = groups.get("day")
    return {
        "kind": "absolute",
        "day_offset": time_lexicon.DAY_OFFSET[day_word] if day_word else None,
        "hour": hour,
        "minute": minute,
        "meridiem": None,
        "hour_is_24h": True,
    }


def _apply_clock_or_part(deadline: dict, groups: _Groups) -> bool:
    if groups.get("hour"):
        clock = _read_clock(groups)
        if clock is None:
            return False
        deadline.update(clock)
        return True
    part = groups.get("part")
    if part is not None:
        deadline["part"] = part
    return True


def _handle_date(groups: _Groups) -> dict | None:
    month = groups.get("month") or groups.get("month2")
    day_num = groups.get("day_num") or groups.get("day_num2")
    if not month or not day_num:
        return None
    month, day_num = to_int(month), to_int(day_num)
    if month is None or day_num is None:
        return None
    if not (1 <= month <= 12 and 1 <= day_num <= 31):
        return None
    deadline = {
        "kind": "date",
        "month": month,
        "day": day_num,
        "year": None,
        "hour": None,
        "minute": None,
        "meridiem": None,
        "hour_is_24h": False,
    }
    return deadline if _apply_clock_or_part(deadline, groups) else None


def _handle_weekday(groups: _Groups) -> dict | None:
    weekday_char = groups.get("weekday")
    if weekday_char is None:
        return None
    weekday = time_lexicon.WEEKDAY_NUMBER[weekday_char]
    prefix = groups.get("week_prefix")
    week_offset = time_lexicon.WEEK_PREFIX[prefix] if prefix else None
    deadline = {
        "kind": "weekday",
        "weekday": weekday,
        "week_offset": week_offset,
        "hour": None,
        "minute": None,
        "meridiem": None,
        "hour_is_24h": False,
    }
    return deadline if _apply_clock_or_part(deadline, groups) else None


_PATTERNS = [
    (
        rf"(?:過|再)?(?P<amount>{_NUM}|半)(?P<unit>{_UNIT})(?:後|內)?(?:{_END})",
        _handle_relative,
    ),
    (rf"限時(?P<amount>{_NUM}|半)(?P<unit>{_UNIT})", _handle_relative),
    (
        rf"(?P<daypart>{_DAYPART})(?:{_CLOCK_CORE})?(?:{_END}|{_BEFORE}(?:{_END})?)",
        _handle_daypart,
    ),
    (
        (
            rf"(?:過|再)?(?P<days>{_NUM})天(?:之?後)?(?:{_CLOCK_NO_DAY})?"
            rf"(?:{_END}|(?:{_BEFORE}|{_WITHIN})(?:{_END})?)"
        ),
        _handle_days_later,
    ),
    (
        (
            rf"(?P<month_end>{_MONTH_END})(?:{_CLOCK_NO_DAY})?"
            rf"(?:{_END}|{_BEFORE}(?:{_END})?)"
        ),
        _handle_month_end,
    ),
    (
        rf"(?P<weekend>{_WEEKEND})(?:{_CLOCK_NO_DAY})?(?:{_END}|{_BEFORE}(?:{_END})?)",
        _handle_weekend,
    ),
    (rf"{_DATE}(?:{_CLOCK_NO_DAY})?(?:{_END}|{_BEFORE}(?:{_END})?)", _handle_date),
    (rf"{_WEEK}(?:{_CLOCK_NO_DAY})?(?:{_END}|{_BEFORE}(?:{_END})?)", _handle_weekday),
    (
        (
            rf"(?:(?P<day>{_DAY}))?(?P<h24>\d{{1,2}}):(?P<m24>\d{{2}})"
            rf"(?:{_END}|{_BEFORE}(?:{_END})?)"
        ),
        _handle_clock24,
    ),
    (
        (
            rf"(?P<day>{_DAY})(?:(?P<part>{_PART}))?"
            rf"(?:{_END}|(?:{_BEFORE}|{_WITHIN})(?:{_END})?)"
        ),
        _handle_no_clock,
    ),
    (rf"(?P<part>{_PART})(?:{_END}|{_BEFORE}(?:{_END})?)", _handle_no_clock),
    (rf"{_CLOCK}(?:{_END})", _handle_absolute),
    (rf"{_CLOCK}(?:{_BEFORE})(?:{_END})?", _handle_absolute),
    (rf"(?:{_LEAD}){_CLOCK}", _handle_absolute),
]
_COMPILED = [(re.compile(pattern), handler) for pattern, handler in _PATTERNS]


def find_candidates(text: str) -> list[dict]:
    candidates = []
    for pattern, handler in _COMPILED:
        for match in pattern.finditer(text):
            value = handler(match.groupdict())
            if value is None:
                continue
            candidates.append(
                {
                    "start": match.start(),
                    "end": match.end(),
                    "label": "TIME",
                    "text": match.group(0),
                    "value": {"deadline": value},
                }
            )
    return candidates


def parse_one(text: str) -> dict | None:
    for candidate in find_candidates(text):
        if candidate["start"] == 0 and candidate["end"] == len(text):
            return candidate["value"]["deadline"]
    return None
