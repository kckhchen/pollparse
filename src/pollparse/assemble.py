from . import lexicon, timeparse
from .normalize import normalize
from .schema import SETTING_KEYS, encode_bio

__all__ = ["build_result"]


# takes a plain text string and the predicted spans as input
# retuens a formatted dictionary for output
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
