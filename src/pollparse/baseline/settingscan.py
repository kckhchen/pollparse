import re

from .. import lexicon
from .._regex import alternation
from ..schema import LEXICON_LABELS

__all__ = ["find_candidates"]


def _pattern_for(label: str) -> str:
    parts = [alternation(lexicon.surfaces(label))]
    if label == "MULTI":
        parts.append(lexicon.LIMIT_PATTERN)
    return "|".join(parts)


_LABEL_PATTERNS = {label: re.compile(_pattern_for(label)) for label in LEXICON_LABELS}


def find_candidates(text: str) -> list[dict]:
    candidates = []
    for label, pattern in _LABEL_PATTERNS.items():
        for match in pattern.finditer(text):
            surface = match.group(0)
            value = lexicon.lookup(surface, label)
            if value is None:
                continue
            candidates.append(
                {
                    "start": match.start(),
                    "end": match.end(),
                    "label": label,
                    "text": surface,
                    "value": value,
                }
            )
    return candidates
