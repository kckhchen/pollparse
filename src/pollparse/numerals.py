__all__ = ["to_int"]

_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "兩": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_UNITS = {"十": 10, "百": 100, "千": 1000}


def to_int(text: str) -> int | None:
    # "二十一" -> 21，"105" -> 105，fallback to None

    if text.isdigit():
        return int(text)

    total, pending_digit = 0, None
    for char in text:
        if char in _DIGITS:
            pending_digit = _DIGITS[char]
        elif char in _UNITS:
            total += (1 if pending_digit is None else pending_digit) * _UNITS[char]
            pending_digit = None
        else:
            return None
    if pending_digit is not None:
        total += pending_digit
    return total
