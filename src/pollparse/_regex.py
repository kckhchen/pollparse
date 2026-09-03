import re
from collections.abc import Iterable

__all__ = ["alternation"]


def alternation(words: Iterable[str]) -> str:
    ordered = sorted(words, key=len, reverse=True)
    return "(?:" + "|".join(re.escape(word) for word in ordered) + ")"
