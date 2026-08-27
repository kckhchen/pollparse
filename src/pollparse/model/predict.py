from pathlib import Path

import torch
from transformers import AutoModelForTokenClassification

from ..baseline.parser import build_result
from ..schema import decode_bio
from .encoding import build_tokenizer, decode_tags, encode

__all__ = ["Tagger"]


class Tagger:
    def __init__(self, model_dir: str | Path, device: str | None = None) -> None:
        model_dir = Path(model_dir)
        self.tokenizer = build_tokenizer(str(model_dir))
        self.model = AutoModelForTokenClassification.from_pretrained(model_dir)
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.model.to(self.device).eval()

    @torch.no_grad()
    def tag(self, text: str) -> list[str]:
        encoded = encode(text, None, self.tokenizer)
        logits = self.model(
            input_ids=torch.tensor([encoded["input_ids"]]).to(self.device),
            attention_mask=torch.tensor([encoded["attention_mask"]]).to(self.device),
        ).logits[0]
        label_ids = logits.argmax(-1).tolist()
        return decode_tags(text, encoded["offsets"], label_ids)

    def spans(self, text: str) -> list[tuple[int, int, str]]:
        return decode_bio(self.tag(text))

    def parse(self, text: str) -> dict:
        return build_result(text, self.spans(text))
