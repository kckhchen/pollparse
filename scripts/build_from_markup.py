import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pollparse import markup
from pollparse.dataset_io import write_jsonl
from pollparse.validate import check_all, coverage_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "inputs", nargs="+", help="Markup files (can pass multiple files)"
    )
    parser.add_argument("output", help="path to output .jsonl")
    args = parser.parse_args()

    examples: list[dict] = []
    for path in args.inputs:
        loaded = markup.load_file(path)
        print(f"  {path}: {len(loaded)} entries")
        for example in loaded:
            example["id"] = len(examples)
            examples.append(example)

    if not examples:
        sys.exit("No examples available")

    result = check_all(examples)
    if result["bad"]:
        print(f"\n✗ {len(result['bad'])} problematic entries：")
        for failure in result["bad"][:10]:
            print("   ", failure)
        sys.exit("Validation failed. No files written.")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output, examples)
    print(f"\n✓ {len(examples)} entries -> {args.output}")

    coverage = coverage_report(examples)
    print("\nCoverage:")
    for label in ("TIME", "MULTI", "ANON", "HOST"):
        total = coverage["total"].get(label, 0)
        missing = coverage["missing"].get(label, 0)
        if total:
            note = "  ← TIME need to be manually labeled" if label == "TIME" else ""
            print(f"  {label:<6} {total - missing}/{total}{note}")
    if coverage["uncovered_phrases"]:
        print(f"  Not inside lexicon: {coverage['uncovered_phrases']}")


if __name__ == "__main__":
    main()
