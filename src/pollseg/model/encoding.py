from transformers import AutoTokenizer, PreTrainedTokenizerFast

from ..schema import ID2TAG, TAG2ID

__all__ = ["SENTINELS", "build_tokenizer", "decode_tags", "encode", "to_model_text"]

SENTINELS = {" ": "␠", "\n": "␤", "\t": "␉"}
_TO_SENTINEL = str.maketrans(SENTINELS)

IGNORE_LABEL = -100


def to_model_text(text: str) -> str:
    converted = text.translate(_TO_SENTINEL)
    assert len(converted) == len(text), "Sentinels changed text length."
    return converted


def build_tokenizer(model_name: str) -> PreTrainedTokenizerFast:
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.add_tokens(list(SENTINELS.values()))
    return tokenizer


def encode(
    text: str,
    tags: list[str] | None,
    tokenizer: PreTrainedTokenizerFast,
    max_length: int = 64,
) -> dict:
    encoded = tokenizer(
        to_model_text(text),
        return_offsets_mapping=True,
        truncation=True,
        max_length=max_length,
    )
    offsets = encoded["offset_mapping"]

    result = {
        "input_ids": encoded["input_ids"],
        "attention_mask": encoded["attention_mask"],
        "offsets": offsets,
    }
    if tags is None:
        return result

    labels = []
    for start, end in offsets:
        if start == end:  # [CLS] / [SEP] / padding
            labels.append(IGNORE_LABEL)
        else:
            labels.append(TAG2ID[tags[start]])
    result["labels"] = labels
    return result


def decode_tags(
    text: str, offsets: list[tuple[int, int]], label_ids: list[int]
) -> list[str]:
    tags = ["O"] * len(text)
    for (start, end), label_id in zip(offsets, label_ids):
        if start == end:
            continue
        tag = ID2TAG[label_id]
        tags[start] = tag
        if tag != "O":
            inside = "I-" + tag.split("-", 1)[1]
            for position in range(start + 1, min(end, len(text))):
                tags[position] = inside
    return tags
