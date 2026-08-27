from pathlib import Path

import torch
from torch.utils.data import Dataset
from transformers import PreTrainedTokenizerFast

from ..dataset_io import read_jsonl
from .encoding import DEFAULT_MAX_LENGTH, IGNORE_LABEL, encode

__all__ = ["TaggingDataset", "collate"]


class TaggingDataset(Dataset):
    def __init__(
        self,
        path: Path,
        tokenizer: PreTrainedTokenizerFast,
        max_length: int = DEFAULT_MAX_LENGTH,
    ) -> None:
        self.rows = read_jsonl(path)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict:
        row = self.rows[index]
        return encode(row["text"], row["tags"], self.tokenizer, self.max_length)


def collate(batch: list[dict], pad_token_id: int) -> dict:
    longest = max(len(item["input_ids"]) for item in batch)
    input_ids = []
    attention_mask = []
    labels = []

    for item in batch:
        padding = longest - len(item["input_ids"])
        input_ids.append(item["input_ids"] + [pad_token_id] * padding)
        attention_mask.append(item["attention_mask"] + [0] * padding)
        labels.append(item["labels"] + [IGNORE_LABEL] * padding)
    return {
        "input_ids": torch.tensor(input_ids),
        "attention_mask": torch.tensor(attention_mask),
        "labels": torch.tensor(labels),
    }
