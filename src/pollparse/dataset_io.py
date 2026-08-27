import json
from pathlib import Path

__all__ = ["read_jsonl", "write_jsonl"]


def read_jsonl(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: str | Path, examples: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.writelines(
            json.dumps(example, ensure_ascii=False) + "\n" for example in examples
        )
