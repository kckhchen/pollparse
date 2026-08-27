import unicodedata

from ..schema import encode_bio
from . import settingscan, timeparse
from .normalize import normalize

__all__ = ["parse"]

_TITLE_MARKERS = "?!:"
_OPTION_DELIMITERS = "、,，/／;|．\n"
_OPTION_CONJUNCTIONS = ("或", "跟", "和")
_TRIM_CATEGORIES = {"So", "Ps", "Pe", "Cc", "Zs"}
_SETTING_KEYS = ("deadline", "multichoice", "max_choices", "anonymous", "host_can_vote")


def parse(text: str) -> dict:
    normalized = normalize(text)

    candidates = timeparse.find_candidates(normalized) + settingscan.find_candidates(
        normalized
    )
    settings_spans = _select(candidates)

    title_range = _split_title(normalized, settings_spans)

    taken = [(span["start"], span["end"]) for span in settings_spans]
    if title_range:
        taken.append(title_range)
        taken.append((title_range[1], title_range[1] + 1))
    option_ranges = _split_options(normalized, _free_ranges(len(normalized), taken))

    spans = []
    if title_range:
        spans.append(
            {
                "start": title_range[0],
                "end": title_range[1],
                "label": "TITLE",
                "text": text[title_range[0] : title_range[1]],
            }
        )
    for start, end in option_ranges:
        spans.append(
            {"start": start, "end": end, "label": "OPT", "text": text[start:end]}
        )
    for span in settings_spans:
        spans.append(
            {
                "start": span["start"],
                "end": span["end"],
                "label": span["label"],
                "text": text[span["start"] : span["end"]],
            }
        )
    spans.sort(key=lambda span: span["start"])

    merged: dict = {}
    for span in settings_spans:
        merged.update(span["value"])

    return {
        "text": text,
        "tags": encode_bio(
            len(text), [(span["start"], span["end"], span["label"]) for span in spans]
        ),
        "spans": spans,
        "target": {
            "title": text[title_range[0] : title_range[1]] if title_range else None,
            "options": [text[start:end] for start, end in option_ranges],
            "settings": {key: merged.get(key) for key in _SETTING_KEYS},
        },
    }


def _select(candidates: list[dict]) -> list[dict]:
    ordered = sorted(candidates, key=lambda c: (-(c["end"] - c["start"]), c["start"]))
    chosen: list[dict] = []
    for candidate in ordered:
        overlaps = any(
            candidate["start"] < taken["end"] and taken["start"] < candidate["end"]
            for taken in chosen
        )
        if not overlaps:
            chosen.append(candidate)
    return sorted(chosen, key=lambda c: c["start"])


def _split_title(text: str, settings: list[dict]) -> tuple[int, int] | None:
    for position, char in enumerate(text):
        if char not in _TITLE_MARKERS:
            continue
        if any(span["start"] <= position < span["end"] for span in settings):
            continue
        return _trim_range(text, 0, position)

    newline = text.find("\n")
    if newline > 0:
        first_line = text[:newline]
        looks_like_one_unit = not any(
            char in _OPTION_DELIMITERS or char.isspace() for char in first_line
        )
        if looks_like_one_unit and not any(
            span["start"] < newline for span in settings
        ):
            return _trim_range(text, 0, newline)
    return None


def _trim_range(text: str, start: int, end: int) -> tuple[int, int] | None:
    while start < end and unicodedata.category(text[start]) in _TRIM_CATEGORIES:
        start += 1
    while end > start and unicodedata.category(text[end - 1]) in _TRIM_CATEGORIES:
        end -= 1
    return (start, end) if start < end else None


def _free_ranges(length: int, taken: list[tuple[int, int]]) -> list[tuple[int, int]]:
    free, cursor = [], 0
    for start, end in sorted(taken):
        if start > cursor:
            free.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < length:
        free.append((cursor, length))
    return free


def _is_delimiter(text: str, position: int) -> bool:
    char = text[position]
    if not (char.isspace() or char in _OPTION_DELIMITERS):
        return False
    inside_a_date = (
        char in "/／"
        and 0 < position < len(text) - 1
        and text[position - 1].isdigit()
        and text[position + 1].isdigit()
    )
    return not inside_a_date


def _split_options(text: str, ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    options: list[tuple[int, int]] = []
    for range_start, range_end in ranges:
        current_start = None
        position = range_start
        while position < range_end:
            for conjunction in _OPTION_CONJUNCTIONS:
                if text.startswith(conjunction, position) and current_start is not None:
                    options.append((current_start, position))
                    current_start = None
                    position += len(conjunction)
                    break
            else:
                if _is_delimiter(text, position):
                    if current_start is not None:
                        options.append((current_start, position))
                        current_start = None
                elif current_start is None:
                    current_start = position
                position += 1
        if current_start is not None:
            options.append((current_start, range_end))
    return [
        trimmed
        for trimmed in (_trim_range(text, start, end) for start, end in options)
        if trimmed is not None
    ]
