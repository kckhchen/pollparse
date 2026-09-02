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
    fatal = _check_length(example)
    if fatal:
        return fatal

    errors = []
    for check in _CHECKS:
        errors.extend(check(example))
    return errors


def _check_length(example):
    tags, text = example["tags"], example["text"]
    if len(tags) != len(text):
        return [f"len mismatch: {len(tags)} tags vs {len(text)} chars"]
    return []


def _check_text_not_empty(example):
    return [] if example["text"].strip() else ["empty text"]


def _check_tags_are_known(example):
    return [
        f"unknown tag {tag}"
        for tag in example["tags"]
        if tag != "O" and tag.split("-", 1)[1] not in SPAN_LABELS
    ]


def _check_tags_match_spans(example):
    recorded = [
        (span["start"], span["end"], span["label"]) for span in example["spans"]
    ]
    if decode_bio(example["tags"]) != recorded:
        return ["BIO decode != recorded spans"]
    return []


def _check_span_geometry(example):
    errors = []
    text = example["text"]
    previous_end = -1
    for span in example["spans"]:
        if span["end"] <= span["start"]:
            errors.append(f"empty span {span}")
        if span["start"] < previous_end:
            errors.append(f"overlapping span {span}")
        previous_end = span["end"]
        if text[span["start"] : span["end"]] != span["text"]:
            errors.append(f"span text mismatch {span}")
    return errors


def _check_single_title(example):
    titles = [span for span in example["spans"] if span["label"] == "TITLE"]
    return ["more than one TITLE span"] if len(titles) > 1 else []


def _check_no_option_before_title(example):
    titles = [span for span in example["spans"] if span["label"] == "TITLE"]
    if not titles or titles[0]["start"] == 0:
        return []
    if any(
        span["end"] <= titles[0]["start"]
        for span in example["spans"]
        if span["label"] == "OPT"
    ):
        return ["OPT span precedes TITLE"]
    return []


def _check_options_have_no_blanks(example):
    if "explicit_sep" in example["meta"]["hard"]:
        return []
    return [
        f"OPT span contains blanks）: {span['text']!r}"
        for span in example["spans"]
        if span["label"] == "OPT" and any(char.isspace() for char in span["text"])
    ]


def _check_options_match_target(example):
    option_texts = [span["text"] for span in example["spans"] if span["label"] == "OPT"]
    errors = []
    if option_texts != example["target"]["options"]:
        errors.append("target.options != OPT spans")
    if not option_texts:
        errors.append("no options")
    return errors


_CHECKS = (
    _check_text_not_empty,
    _check_tags_are_known,
    _check_tags_match_spans,
    _check_span_geometry,
    _check_single_title,
    _check_no_option_before_title,
    _check_options_have_no_blanks,
    _check_options_match_target,
)
