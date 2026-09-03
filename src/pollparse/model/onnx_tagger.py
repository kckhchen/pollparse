from pathlib import Path

import numpy as np
from tokenizers import Tokenizer

from ..assemble import build_result
from ..schema import ID2TAG, decode_bio
from .encoding import DEFAULT_MAX_LENGTH, decode_tags, to_model_text

__all__ = ["OnnxTagger"]

ONNX_NAME = "model.onnx"
TOKENIZER_NAME = "tokenizer.json"


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=-1, keepdims=True)
    exponentiated = np.exp(shifted)
    return exponentiated / exponentiated.sum(axis=-1, keepdims=True)


class OnnxTagger:
    def __init__(
        self,
        model_dir: str | Path,
        max_length: int = DEFAULT_MAX_LENGTH,
        threads: int = 1,
    ) -> None:
        import onnxruntime as ort

        model_dir = Path(model_dir)
        self.tokenizer = Tokenizer.from_file(str(model_dir / TOKENIZER_NAME))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.max_length = max_length

        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = threads
        self.session = ort.InferenceSession(
            str(model_dir / ONNX_NAME),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )

    def _predict(self, text: str) -> tuple[list[str], list[float], bool]:
        encoded = self.tokenizer.encode(to_model_text(text))
        truncated = len(encoded.ids) > self.max_length
        ids = encoded.ids[: self.max_length]
        offsets = encoded.offsets[: self.max_length]

        outputs = self.session.run(
            None,
            {
                "input_ids": np.array([ids], dtype=np.int64),
                "attention_mask": np.ones((1, len(ids)), dtype=np.int64),
            },
        )
        logits = np.asarray(outputs[0])[0]
        probabilities = _softmax(logits)

        label_ids = probabilities.argmax(-1).tolist()
        tags = decode_tags(text, offsets, label_ids)

        char_confidence = [0.0] * len(text)
        for (start, end), row in zip(offsets, probabilities.max(-1).tolist()):
            if start == end:
                continue
            for position in range(start, min(end, len(text))):
                char_confidence[position] = row
        return tags, char_confidence, truncated

    def spans(self, text: str) -> list[tuple[int, int, str]]:
        return decode_bio(self._predict(text)[0])

    def parse(self, text: str) -> dict:
        tags, char_confidence, truncated = self._predict(text)
        result = build_result(text, decode_bio(tags))

        for span in result["spans"]:
            span["confidence"] = min(
                char_confidence[span["start"] : span["end"]], default=0.0
            )
        result["confidence"] = min(char_confidence, default=0.0)
        result["truncated"] = truncated
        return result

    @property
    def labels(self) -> dict[int, str]:
        return ID2TAG
