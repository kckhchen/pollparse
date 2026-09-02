from dataclasses import dataclass, field
from typing import Any

# all labels as a list. These are imported to other modules and serve as the ground truth.
SPAN_LABELS = ["TITLE", "OPT", "TIME", "MULTI", "ANON", "HOST", "LIVE", "ADDOPT"]
SETTING_LABELS = ["TIME", "MULTI", "ANON", "HOST", "LIVE", "ADDOPT"]

# setting labels that can be resolved with simple lexicon lookups. Everything but time (requires now).
LEXICON_LABELS = [label for label in SETTING_LABELS if label != "TIME"]

# for api
SETTING_KEYS = (
    "deadline",
    "multichoice",
    "max_choices",
    "anonymous",
    "host_can_vote",
    "live_results",
    "allow_other",
)

# all legitimate BIO tags
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


def encode_bio(length, spans):
    for _, _, label in spans:
        if label not in SPAN_LABELS:
            raise ValueError(f"unknown span label: {label!r}")
    # from span to BIO tags
    tags = ["O"] * length
    for start, end, label in spans:
        tags[start] = f"B-{label}"
        for position in range(start + 1, end):
            tags[position] = f"I-{label}"
    return tags


def decode_bio(tags):
    # from BIO tags to span
    spans = []
    current = None
    for idx, tag in enumerate(tags):
        if tag == "O":
            if current:
                spans.append(current)
                current = None
            continue
        prefix, label = tag.split("-", 1)
        if prefix == "B" or current is None or current[2] != label:
            if current:
                spans.append(current)
            current = (idx, idx + 1, label)
        else:
            current = (current[0], idx + 1, label)
    if current:
        spans.append(current)
    return spans
