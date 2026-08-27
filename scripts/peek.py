import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pollseg.dataset_io import read_jsonl

LABEL_COLOR = {
    "TITLE": "\033[95m",
    "OPT": "\033[92m",
    "TIME": "\033[93m",
    "MULTI": "\033[96m",
    "ANON": "\033[94m",
    "HOST": "\033[91m",
}
RESET = "\033[0m"


def colorize(example):
    parts, scan_position = [], 0
    for span in example["spans"]:
        before_span = example["text"][scan_position : span["start"]]
        parts.append(before_span.replace("\n", "⏎"))
        parts.append(
            LABEL_COLOR[span["label"]] + span["text"].replace("\n", "⏎") + RESET
        )
        scan_position = span["end"]
    parts.append(example["text"][scan_position:].replace("\n", "⏎"))
    return "".join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("-n", "--count", type=int, default=12)
    parser.add_argument(
        "--hard", default=None, help="Only peek examples with certain hard flag"
    )
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    examples = read_jsonl(args.path)
    if args.hard:
        examples = [
            example for example in examples if args.hard in example["meta"]["hard"]
        ]
    if not examples:
        sys.exit("No matching examples")

    legend = " ".join(LABEL_COLOR[label] + label + RESET for label in LABEL_COLOR)
    print(legend, f"  ({len(examples)} exmaples available)\n")

    sample_size = min(args.count, len(examples))
    for example in random.Random(args.seed).sample(examples, sample_size):
        print(colorize(example))
        settings = {
            key: value
            for key, value in example["target"]["settings"].items()
            if value is not None
        }
        print(f"   -> options={example['target']['options']}")
        print(f"      settings={settings}  hard={example['meta']['hard']}\n")


if __name__ == "__main__":
    main()
