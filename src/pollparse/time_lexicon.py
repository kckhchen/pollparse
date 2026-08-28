__all__ = [
    "BEFORE_MARKERS",
    "DAY_OFFSET",
    "DAY_WORDS",
    "DURATION_UNITS",
    "END_MARKERS",
    "LEAD_VERBS",
    "MERIDIEM_OF",
    "MIDNIGHT_AT_TWELVE",
    "PART_END",
    "PART_KIND",
    "PART_WORDS",
    "PM_FROM",
    "WEEKDAY_CHARS",
    "WEEK_PREFIX",
    "meridiem_of",
    "to_24_hour",
]

DAY_WORDS: list[tuple[str, int]] = [
    ("今天", 0),
    ("明天", 1),
    ("後天", 2),
    ("大後天", 3),
]
DAY_OFFSET: dict[str, int] = dict(DAY_WORDS)

PART_WORDS: list[tuple[str, str]] = [
    ("早上", "am"),
    ("上午", "am"),
    ("中午", "noon"),
    ("下午", "pm"),
    ("晚上", "pm"),
    ("傍晚", "dusk"),
    ("晚間", "pm"),
    ("凌晨", "dawn"),
    ("半夜", "dawn"),
    ("午夜", "dawn"),
]
PART_KIND: dict[str, str] = dict(PART_WORDS)

MERIDIEM_OF: dict[str, str] = {
    "am": "am",
    "noon": "pm",
    "pm": "pm",
    "dusk": "pm",
    "dawn": "am",
}

MIDNIGHT_AT_TWELVE: frozenset[str] = frozenset(
    {"早上", "上午", "晚上", "晚間", "凌晨", "半夜", "午夜"}
)

PM_FROM: dict[str, int] = {
    "下午": 1,
    "傍晚": 1,
    "晚上": 5,
    "晚間": 5,
}

PART_END: dict[str, tuple[int, int, int]] = {
    "早上": (12, 0, 0),
    "上午": (12, 0, 0),
    "中午": (12, 0, 0),
    "下午": (18, 0, 0),
    "傍晚": (19, 0, 0),
    "晚上": (23, 59, 59),
    "晚間": (23, 59, 59),
    "凌晨": (23, 59, 59),
    "半夜": (23, 59, 59),
    "午夜": (23, 59, 59),
}

END_MARKERS = ["截止", "收單", "結束", "關閉", "到期", "停止投票", "截止投票"]
BEFORE_MARKERS = ["前", "之前", "以前", "為止"]
LEAD_VERBS = ["到", "開放到", "投到", "最晚", "限", "投票到"]

DURATION_UNITS: list[tuple[str, int]] = [
    ("秒", 1),
    ("分", 60),
    ("分鐘", 60),
    ("小時", 3600),
    ("鐘頭", 3600),
]
SECONDS_PER_UNIT: dict[str, int] = dict(DURATION_UNITS)

WEEKDAY_CHARS: list[tuple[str, int]] = [
    ("一", 1),
    ("二", 2),
    ("三", 3),
    ("四", 4),
    ("五", 5),
    ("六", 6),
    ("日", 7),
    ("天", 7),
]
WEEKDAY_NUMBER: dict[str, int] = dict(WEEKDAY_CHARS)

WEEK_PREFIX: dict[str, int] = {"這": 0, "本": 0, "下": 1}


def to_24_hour(hour: int, part_word: str | None) -> int:
    if hour == 12:
        return 0 if part_word in MIDNIGHT_AT_TWELVE else 12
    if part_word is None:
        return hour % 24
    if PART_KIND.get(part_word) == "noon":
        return 12
    pm_from = PM_FROM.get(part_word)
    if pm_from is not None and pm_from <= hour < 12:
        return hour + 12
    return hour % 24


def meridiem_of(part_word: str | None) -> str | None:
    if not part_word:
        return None
    time_part = PART_KIND.get(part_word)
    return MERIDIEM_OF.get(time_part) if time_part else None
