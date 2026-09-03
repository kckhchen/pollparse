from pathlib import Path

import pytest

from pollparse.markup import TAG_MAP, load_file
from pollparse.validate import check_all, coverage_report


@pytest.fixture
def write(tmp_path):
    def _write(*lines):
        path = tmp_path / "sample.txt"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return load_file(path)

    return _write


def test_strip_tags_reveals_plain_texts(write):
    example = write("<t>晚餐吃什麼</t>？<o>披薩</o> <o>牛肉麵</o>")[0]
    assert example["text"] == "晚餐吃什麼？披薩 牛肉麵"


def test_span_can_recover_original(write):
    example = write(
        "<t>晚餐吃什麼</t>？<o>披薩</o> <o>牛肉麵</o> <time>九點截止</time><multi>可複選</multi>"
    )[0]
    for span in example["spans"]:
        assert example["text"][span["start"] : span["end"]] == span["text"]


def test_tags_map_to_labels_correctly(write):
    example = write(
        "<t>晚餐</t>？<o>披薩</o> <time>九點截止</time><anon>匿名</anon>"
        "<host>房主不投</host><live>即時開票</live><addopt>可以新增</addopt>"
    )[0]
    got = {span["label"]: span["text"] for span in example["spans"]}
    assert got["TITLE"] == "晚餐"
    assert got["TIME"] == "九點截止"
    assert got["ANON"] == "匿名"
    assert got["HOST"] == "房主不投"
    assert got["LIVE"] == "即時開票"
    assert got["ADDOPT"] == "可以新增"


def test_supported_tags_can_be_parsed(write):
    for short, label in TAG_MAP.items():
        example = write(f"<{short}>測試</{short}>")[0]
        assert example["spans"][0]["label"] == label


def test_meaning_is_correct(write):
    example = write("<t>晚餐</t>？<o>A</o> <multi>可複選</multi><anon>匿名</anon>")[0]
    settings = example["target"]["settings"]
    assert settings.get("multichoice") is True
    assert settings.get("anonymous") is True


def test_markup_and_parser_align(write):
    from pollparse.baseline.parser import parse
    from pollparse.schema import SETTING_KEYS

    plain = "晚餐吃什麼？披薩 牛肉麵 可複選匿名房主不投即時開票可以新增"
    marked = (
        "<t>晚餐吃什麼</t>？<o>披薩</o> <o>牛肉麵</o> "
        "<multi>可複選</multi><anon>匿名</anon><host>房主不投</host>"
        "<live>即時開票</live><addopt>可以新增</addopt>"
    )
    gold = write(marked)[0]
    assert gold["text"] == plain

    gold_settings = gold["target"]["settings"]
    predicted = parse(plain)["target"]["settings"]
    for key in SETTING_KEYS:
        if key == "deadline":
            continue
        assert gold_settings.get(key) == predicted.get(key), key


def test_time_unresolved_should_be_marked(write):
    example = write("<t>晚餐</t>？<o>A</o> <time>九點截止</time>")[0]
    assert example["target"]["settings"].get("deadline") is None
    gaps = example["meta"].get("unresolved", [])
    assert any(gap["label"] == "TIME" for gap in gaps), "Time gap is not marked"


EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.mark.parametrize("name", ["train.txt", "dev.txt"])
def test_example_markup_still_parses(name):
    examples = load_file(EXAMPLES / name)
    assert examples
    assert not check_all(examples)["bad"]


def test_example_settings_are_all_in_the_lexicon():
    for name in ("train.txt", "dev.txt"):
        report = coverage_report(load_file(EXAMPLES / name))
        assert report["uncovered_phrases"] == []


def test_example_splits_share_no_option_vocabulary():
    def options(name):
        return {
            span["text"]
            for example in load_file(EXAMPLES / name)
            for span in example["spans"]
            if span["label"] == "OPT"
        }

    assert not options("train.txt") & options("dev.txt")
