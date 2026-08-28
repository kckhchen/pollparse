from pathlib import Path

import torch
from transformers import AutoModelForTokenClassification

from ..baseline.parser import build_result
from ..schema import decode_bio
from .encoding import DEFAULT_MAX_LENGTH, build_tokenizer, decode_tags, encode

__all__ = ["Tagger"]


class Tagger:
    def __init__(
        self,
        model_dir: str | Path,
        device: str | None = None,
        max_length: int = DEFAULT_MAX_LENGTH,
    ) -> None:
        self.max_length = max_length
        model_dir = Path(model_dir)
        self.tokenizer = build_tokenizer(str(model_dir))
        self.model = AutoModelForTokenClassification.from_pretrained(model_dir)
        # not using mps in inference due to overhead
        self.device = device or "cpu"
        self.model.to(self.device).eval()

    @torch.no_grad()
    def _predict(self, text: str) -> tuple[list[str], list[float]]:
        encoded = encode(text, None, self.tokenizer, max_length=self.max_length)
        logits = self.model(
            input_ids=torch.tensor([encoded["input_ids"]]).to(self.device),
            attention_mask=torch.tensor([encoded["attention_mask"]]).to(self.device),
        ).logits[0]
        probabilities = logits.softmax(-1).max(-1).values.tolist()
        label_ids = logits.argmax(-1).tolist()

        tags = decode_tags(text, encoded["offsets"], label_ids)
        char_confidence = [0.0] * len(text)
        for (start, end), probability in zip(encoded["offsets"], probabilities):
            if start == end:
                continue
            for position in range(start, min(end, len(text))):
                char_confidence[position] = probability
        return tags, char_confidence

    def tag(self, text: str) -> list[str]:
        return self._predict(text)[0]

    def spans(self, text: str) -> list[tuple[int, int, str]]:
        return decode_bio(self.tag(text))

    def parse(self, text: str) -> dict:
        tags, char_confidence = self._predict(text)
        result = build_result(text, decode_bio(tags))

        for span in result["spans"]:
            span["confidence"] = min(
                char_confidence[span["start"] : span["end"]], default=0.0
            )
        result["confidence"] = min(char_confidence, default=0.0)
        return result
