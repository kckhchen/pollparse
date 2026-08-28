import pytest

from pollparse.model.encoding import SENTINELS, decode_tags, to_model_text


@pytest.mark.parametrize(
    "text",
    [
        "晚餐吃什麼？披薩 牛肉麵 水餃",
        "題目\n選項一\n選項二",
        "a\tb",
        "沒有任何空白",
        "",
        "   ",
    ],
)
def test_len_consistent_on_sentinel_change(text):
    assert len(to_model_text(text)) == len(text)


def test_spaces_are_swapped():
    converted = to_model_text("a b\nc\td")
    assert not any(char.isspace() for char in converted)
    for original, sentinel in SENTINELS.items():
        assert sentinel in to_model_text(f"x{original}y")


def test_non_spaces_are_kept():
    text = "晚餐吃什麼？披薩 牛肉麵"
    converted = to_model_text(text)
    for index, char in enumerate(text):
        if not char.isspace():
            assert converted[index] == char


def test_sentinel_is_uncommon():
    for sentinel in SENTINELS.values():
        assert not sentinel.isascii()
        assert not sentinel.isalnum()


def test_one_label_per_char():
    text = "披薩 牛肉麵"
    offsets = [(0, 0), (0, 2), (3, 6), (0, 0)]
    label_ids = [0, 3, 3, 0]  # 0=O, 3=B-OPT
    tags = decode_tags(text, offsets, label_ids)
    assert len(tags) == len(text)


def test_entire_word_get_same_label():
    text = "披薩"
    tags = decode_tags(text, [(0, 0), (0, 2), (0, 0)], [0, 3, 0])
    assert tags[0].endswith("OPT") and tags[1].endswith("OPT")


def test_skipped_words_stll_have_tags():
    text = "披薩 牛肉麵"
    tags = decode_tags(text, [(0, 0), (0, 2), (3, 6), (0, 0)], [0, 3, 3, 0])
    assert tags[2] is not None
