import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pollparse.baseline.parser import parse as parse_with_rules
from pollparse.dataset_io import read_jsonl
from pollparse.schema import SETTING_KEYS

OUT = ROOT / "dist"


def _spans_of(example: dict) -> set[tuple[int, int, str]]:
    return {(span["start"], span["end"], span["label"]) for span in example["spans"]}


def _settings_match(gold: dict, predicted: dict, skip: set[str]) -> bool:
    gold_settings = gold["target"]["settings"]
    predicted_settings = predicted["target"]["settings"]
    return all(
        gold_settings.get(key) == predicted_settings.get(key)
        for key in SETTING_KEYS
        if key not in skip
    )


def evaluate(examples: list[dict], parse) -> dict:
    hits = Counter()
    gold_totals = Counter()
    predicted_totals = Counter()
    totals = Counter()
    by_flag = defaultdict(Counter)

    for example in examples:
        predicted = parse(example["text"])

        gold_spans, predicted_spans = _spans_of(example), _spans_of(predicted)
        for start, end, label in gold_spans:
            gold_totals[label] += 1
            if (start, end, label) in predicted_spans:
                hits[label] += 1
        for _, _, label in predicted_spans:
            predicted_totals[label] += 1

        skip = {
            "deadline"
            for gap in example["meta"].get("unresolved", [])
            if gap["label"] == "TIME"
        }
        options_ok = example["target"]["options"] == predicted["target"]["options"]
        title_ok = example["target"]["title"] == predicted["target"]["title"]
        settings_ok = _settings_match(example, predicted, skip)
        exact = options_ok and title_ok and settings_ok

        totals["n"] += 1
        totals["options"] += options_ok
        totals["title"] += title_ok
        totals["settings"] += settings_ok
        totals["exact"] += exact
        for flag in example["meta"]["hard"] or ["(none)"]:
            by_flag[flag]["n"] += 1
            by_flag[flag]["exact"] += exact

    labels = sorted(set(gold_totals) | set(predicted_totals))
    span_scores = {}
    for label in labels:
        precision = (
            hits[label] / predicted_totals[label] if predicted_totals[label] else 0.0
        )
        recall = hits[label] / gold_totals[label] if gold_totals[label] else 0.0
        f1 = (
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
        span_scores[label] = {
            "p": precision,
            "r": recall,
            "f1": f1,
            "gold": gold_totals[label],
        }
    return {"totals": totals, "spans": span_scores, "by_flag": by_flag}


def _print_report(name: str, report: dict, show_slices: bool) -> None:
    totals = report["totals"]
    count = totals["n"]
    print(f"\n=== {name}  (n={count}) ===")
    print(f"  {'label':<8}{'P':>8}{'R':>8}{'F1':>8}{'gold':>8}")
    for label, score in report["spans"].items():
        print(
            f"  {label:<8}{score['p']:>8.3f}{score['r']:>8.3f}"
            f"{score['f1']:>8.3f}{score['gold']:>8}"
        )
    print(f"  {'-' * 40}")
    for key, caption in (
        ("title", "Correct title"),
        ("options", "Correct options"),
        ("settings", "Correct settings"),
        ("exact", "Correct on everything"),
    ):
        marker = "  <<<" if key == "exact" else ""
        print(f"  {caption:<10}{totals[key] / count:>8.1%}{marker}")

    if show_slices:
        print("Slice based on hard flag")
        rows = sorted(
            report["by_flag"].items(), key=lambda item: item[1]["exact"] / item[1]["n"]
        )
        for flag, counts in rows:
            print(
                f"    {flag:<18}{counts['exact'] / counts['n']:>7.1%}"
                f"  (n={counts['n']})"
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", action="store_true", help="Slice based on hard flag")
    parser.add_argument(
        "--splits", nargs="*", default=["dev_iid", "dev_oov", "eval_real"]
    )
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument(
        "--baseline", action="store_true", help="Evaluate the rule baseline"
    )
    which.add_argument("--model", help="Directory of a trained tagger")
    args = parser.parse_args()

    if args.baseline:
        parse = parse_with_rules
        print("parser: rule baseline")
    else:
        if not Path(args.model).exists():
            sys.exit(
                f"{args.model} not found — train one with scripts/train_model.py, "
                "or pass --baseline to evaluate the rules"
            )
        from pollparse.model.predict import Tagger

        parse = Tagger(args.model).parse
        print(f"parser: model at {args.model}")

    for split in args.splits:
        path = OUT / f"{split}.jsonl"
        if not path.exists():
            print(f"（skipped {split}：{path} does not exist）")
            continue
        examples = read_jsonl(path)
        _print_report(split, evaluate(examples, parse), args.slice)


if __name__ == "__main__":
    main()
