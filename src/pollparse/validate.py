from collections import Counter

from .schema import SETTING_LABELS, SPAN_LABELS, decode_bio


def coverage_report(examples):
    span_counts = Counter()
    missing_counts = Counter()
    uncovered_phrases = []
    for example in examples:
        for span in example["spans"]:
            if span["label"] in SETTING_LABELS:
                span_counts[span["label"]] += 1
        for gap in example["meta"].get("unresolved", []):
            missing_counts[gap["label"]] += 1
            if gap["label"] != "TIME":
                uncovered_phrases.append(gap["text"])
    return {
        "total": dict(span_counts),
        "missing": dict(missing_counts),
        "uncovered_phrases": sorted(set(uncovered_phrases)),
    }


def check_all(examples):
    failures = []
    total = 0
    for example in examples:
        total += 1
        errors = _check(example)
        if errors:
            failures.append((example.get("id"), example["text"], errors))
    return {"total": total, "bad": failures}


def _check(example):
    errors = []
    text = example["text"]
    tags = example["tags"]

    if len(tags) != len(text):
        errors.append(f"len mismatch: {len(tags)} tags vs {len(text)} chars")
        return errors
    if not text.strip():
        errors.append("empty text")

    for tag in tags:
        if tag != "O" and tag.split("-", 1)[1] not in SPAN_LABELS:
            errors.append(f"unknown tag {tag}")

    recorded = [
        (span["start"], span["end"], span["label"]) for span in example["spans"]
    ]
    if decode_bio(tags) != recorded:
        errors.append("BIO decode != recorded spans")

    previous_end = -1
    for span in example["spans"]:
        if span["end"] <= span["start"]:
            errors.append(f"empty span {span}")
        if span["start"] < previous_end:
            errors.append(f"overlapping span {span}")
        previous_end = span["end"]
        if text[span["start"] : span["end"]] != span["text"]:
            errors.append(f"span text mismatch {span}")

    title_spans = [span for span in example["spans"] if span["label"] == "TITLE"]
    if len(title_spans) > 1:
        errors.append("more than one TITLE span")
    if (
        title_spans
        and title_spans[0]["start"] > 0
        and any(
            span["end"] <= title_spans[0]["start"]
            for span in example["spans"]
            if span["label"] != "TITLE"
        )
    ):
        errors.append("TITLE is not the first labelled span")

    if "explicit_sep" not in example["meta"]["hard"]:
        for span in example["spans"]:
            if span["label"] == "OPT" and any(ch.isspace() for ch in span["text"]):
                errors.append(f"OPT span contains blanks）: {span['text']!r}")

    option_texts = [span["text"] for span in example["spans"] if span["label"] == "OPT"]
    if option_texts != example["target"]["options"]:
        errors.append("target.options != OPT spans")
    if len(option_texts) == 0:
        errors.append("no options")

    return errors
