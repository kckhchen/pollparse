from dataclasses import dataclass, field
from typing import Any

SPAN_LABELS = ["TITLE", "OPT", "TIME", "MULTI", "ANON", "HOST", "LIVE", "ADDOPT"]
SETTING_LABELS = ["TIME", "MULTI", "ANON", "HOST", "LIVE", "ADDOPT"]

# 靠詞庫查表就解得出語意的設定標籤。TIME 不在裡面 —— 它走 timeparse 的文法，
# 不是查表。
LEXICON_LABELS = [label for label in SETTING_LABELS if label != "TIME"]

# API 回傳的設定欄位。這裡是唯一的定義點，parser、eval、app 都從這裡拿，
# 加一個設定就不用再去翻有哪幾個檔案寫死了同一份清單。
SETTING_KEYS = (
    "deadline",
    "multichoice",
    "max_choices",
    "anonymous",
    "host_can_vote",
    "live_results",
    "allow_other",
)

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
