import re
from collections.abc import Iterable

__all__ = ["alternation"]


def alternation(words: Iterable[str]) -> str:
    return "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))
