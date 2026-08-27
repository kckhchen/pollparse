import re
from itertools import pairwise

from . import lexicon
from .schema import encode_bio

TAG_MAP = {
    "t": "TITLE",
    "o": "OPT",
    "time": "TIME",
    "multi": "MULTI",
    "anon": "ANON",
    "host": "HOST",
}
__all__ = ["load_file"]

_PATTERN = re.compile(r"<(t|o|time|multi|anon|host)>(.*?)</\1>", re.DOTALL)


def load_file(path):
    examples = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            line = line.replace("\\n", "\n")
            examples.append(_parse(line, len(examples)))
    return examples


def _parse(line, id=0):
    text, spans = _strip_markup(line)
    settings, unresolved = _resolve_settings(spans)
    tags = encode_bio(
        len(text),
        [(span["start"], span["end"], span["label"]) for span in spans],
    )

    return {
        "id": id,
        "text": text,
        "tags": tags,
        "spans": spans,
        "target": {
            "title": next(
                (span["text"] for span in spans if span["label"] == "TITLE"), None
            ),
            "options": [span["text"] for span in spans if span["label"] == "OPT"],
            "settings": settings,
        },
        "meta": {
            "domain": "real",
            "n_options": sum(1 for span in spans if span["label"] == "OPT"),
            "unresolved": unresolved,
            "hard": _detect_hard_flags(text, spans),
        },
    }


def _strip_markup(line):
    # "<t>晚餐</t>？<o>披薩</o>"  ->  ("晚餐？披薩", [TITLE 0..2, OPT 3..5])
    text_fragments = []
    spans = []
    line_position = 0
    text_position = 0

    for match in _PATTERN.finditer(line):
        untagged_text = line[line_position : match.start()]
        text_fragments.append(untagged_text)
        text_position += len(untagged_text)

        span_text = match.group(2)
        spans.append(
            {
                "start": text_position,
                "end": text_position + len(span_text),
                "label": TAG_MAP[match.group(1)],
                "text": span_text,
            }
        )
        text_fragments.append(span_text)
        text_position += len(span_text)
        line_position = match.end()

    text_fragments.append(line[line_position:])
    return "".join(text_fragments), spans


_EXPLICIT_DELIMITERS = "、／/"


def _detect_hard_flags(text: str, spans: list[dict]) -> list[str]:
    options = [span for span in spans if span["label"] == "OPT"]
    for previous, following in pairwise(options):
        separator = text[previous["end"] : following["start"]]
        if any(char in _EXPLICIT_DELIMITERS for char in separator):
            return ["explicit_sep"]
    return []


def _resolve_settings(spans):
    settings = {}
    unresolved = []
    for span in spans:
        if span["label"] in ("MULTI", "ANON", "HOST"):
            value = lexicon.lookup(span["text"], span["label"])
            if value:
                settings.update(value)
            else:
                unresolved.append(
                    {
                        "label": span["label"],
                        "text": span["text"],
                        "why": "Not in lexicon",
                    }
                )
        elif span["label"] == "TIME":
            unresolved.append(
                {"label": "TIME", "text": span["text"], "why": "Need manual labelling"}
            )
    return settings, unresolved
