from itertools import pairwise

import pytest

from pollparse.baseline.parser import parse

SAMPLES = [
    "晚餐吃什麼？披薩 牛肉麵 水餃 拉麵 九點截止可複選匿名房主不投票",
    "午餐吃啥 便當 麵 沙拉",
    "要不要辦？要 不要",
    "幾點集合？八點 八點半 九點 晚上十點截止",
    "【投票】尾牙吃什麼：火鍋 燒肉 熱炒 可以多選",
    "晚餐吃什麼？\n披薩\n牛肉麵\n水餃",
    "晚餐吃什麼？披薩 牛肉麵 九點截止可複選匿名即時開票可以新增",
    "投票？ＡＢ ＣＤ ９點截止",
]


@pytest.mark.parametrize("text", SAMPLES)
def test_span_should_reveal_original(text):
    for span in parse(text)["spans"]:
        assert text[span["start"] : span["end"]] == span["text"]


@pytest.mark.parametrize("text", SAMPLES)
def test_span_not_overlapped_and_sorted(text):
    spans = parse(text)["spans"]
    for previous, current in pairwise(spans):
        assert previous["end"] <= current["start"]


@pytest.mark.parametrize("text", SAMPLES)
def test_tag_and_plain_text_same_length(text):
    assert len(parse(text)["tags"]) == len(text)


@pytest.mark.parametrize("text", SAMPLES)
def test_title_is_first_labelled_span(text):
    spans = parse(text)["spans"]
    titles = [s for s in spans if s["label"] == "TITLE"]
    assert len(titles) <= 1
    if titles:
        assert spans[0]["label"] == "TITLE"


@pytest.mark.parametrize("text", SAMPLES)
def test_option_is_not_empty(text):
    for option in parse(text)["target"]["options"]:
        assert option == option.strip() != ""


def test_not_in_lexicon_becomes_options():
    result = parse("續攤要幹嘛？KTV 喝酒 大家自己看著辦")["target"]
    assert "大家自己看著辦" in result["options"]
    assert all(v is None for k, v in result["settings"].items() if k != "deadline")


def test_gold_sentence_test():
    result = parse("晚餐吃什麼？披薩 牛肉麵 水餃 拉麵 九點截止可複選匿名房主不投票")[
        "target"
    ]
    assert result["title"] == "晚餐吃什麼"
    assert result["options"] == ["披薩", "牛肉麵", "水餃", "拉麵"]
    assert result["settings"]["multichoice"] is True
    assert result["settings"]["anonymous"] is True
    assert result["settings"]["host_can_vote"] is False
    assert result["settings"]["deadline"] is not None


def test_no_question_mark_no_title():
    assert parse("午餐吃啥 便當 麵 沙拉")["target"]["title"] is None


def test_consecutive_options_are_parsed_correctly():
    settings = parse("晚餐？A B 九點截止可複選匿名即時開票可以新增房主不投")["target"][
        "settings"
    ]
    assert settings["multichoice"] is True
    assert settings["anonymous"] is True
    assert settings["live_results"] is True
    assert settings["allow_other"] is True
    assert settings["host_can_vote"] is False
    assert settings["deadline"] is not None


def test_return_none_on_no_config():
    settings = parse("晚餐吃什麼？披薩 牛肉麵")["target"]["settings"]
    assert all(value is None for value in settings.values())


@pytest.mark.parametrize("text", ["", " ", "？", "\n\n", "。", "A"])
def test_wont_crash_on_degenerate_input(text):
    result = parse(text)
    assert len(result["tags"]) == len(text)
