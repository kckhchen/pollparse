import unicodedata

from .. import lexicon, timeparse
from ..normalize import normalize
from ..schema import SETTING_KEYS, encode_bio
from . import settingscan

__all__ = [
    "EXPLICIT_DELIMITERS",
    "OPTION_CONJUNCTIONS",
    "OPTION_DELIMITERS",
    "build_result",
    "parse",
    "spans_from_rules",
]

_TITLE_MARKERS = "?!:"

OPTION_DELIMITERS = "、,，/／;|．\n"
EXPLICIT_DELIMITERS = "、／/"
OPTION_CONJUNCTIONS = ("或",)
_TRIM_CATEGORIES = {"So", "Ps", "Pe", "Cc", "Zs"}


def spans_from_rules(text: str) -> list[tuple[int, int, str]]:
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

    spans: list[tuple[int, int, str]] = []
    if title_range:
        spans.append((title_range[0], title_range[1], "TITLE"))
    spans.extend((start, end, "OPT") for start, end in option_ranges)
    spans.extend((span["start"], span["end"], span["label"]) for span in settings_spans)
    return sorted(spans)


def build_result(text: str, spans: list[tuple[int, int, str]]) -> dict:
    normalized = normalize(text)

    settings: dict = {}
    for span_start, span_end, label in spans:
        if label in ("TITLE", "OPT"):
            continue
        surface = normalized[span_start:span_end]
        if label == "TIME":
            deadline = timeparse.parse_one(surface)
            if deadline is not None:
                settings["deadline"] = deadline
        else:
            value = lexicon.lookup(surface, label)
            if value is not None:
                settings.update(value)

    return {
        "text": text,
        "tags": encode_bio(len(text), spans),
        "spans": [
            {"start": s, "end": e, "label": label, "text": text[s:e]}
            for s, e, label in spans
        ],
        "target": {
            "title": next(
                (text[s:e] for s, e, label in spans if label == "TITLE"), None
            ),
            "options": [text[s:e] for s, e, label in spans if label == "OPT"],
            "settings": {key: settings.get(key) for key in SETTING_KEYS},
        },
    }


def parse(text: str) -> dict:
    spans = spans_from_rules(text)
    return build_result(text, spans)


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
            char in OPTION_DELIMITERS or char.isspace() for char in first_line
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
    if not (char.isspace() or char in OPTION_DELIMITERS):
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
            for conjunction in OPTION_CONJUNCTIONS:
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
