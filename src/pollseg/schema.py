from dataclasses import dataclass, field
from typing import Any

SPAN_LABELS = ["TITLE", "OPT", "TIME", "MULTI", "ANON", "HOST"]
SETTING_LABELS = ["TIME", "MULTI", "ANON", "HOST"]

TAGS = ["O"] + [f"{prefix}-{label}" for label in SPAN_LABELS for prefix in ("B", "I")]
TAG2ID = {tag: index for index, tag in enumerate(TAGS)}
ID2TAG = {index: tag for tag, index in TAG2ID.items()}


@dataclass
class Phrase:
    text: str
    label: str
    value: dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    start: int
    end: int
    label: str

    @property
    def length(self) -> int:
        return self.end - self.start
