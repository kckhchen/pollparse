import pytest

from pollparse.schema import SPAN_LABELS, TAGS, decode_bio, encode_bio


def test_each_label_has_B_and_I():
    for label in SPAN_LABELS:
        assert f"B-{label}" in TAGS
        assert f"I-{label}" in TAGS
    assert TAGS[0] == "O"
    assert len(TAGS) == len(SPAN_LABELS) * 2 + 1


def test_tags_same_len_as_char():
    assert len(encode_bio(5, [])) == 5
    assert len(encode_bio(5, [(0, 2, "OPT")])) == 5


def test_all_O_if_no_spans():
    assert encode_bio(3, []) == ["O", "O", "O"]


def test_all_B_if_one_char():
    assert encode_bio(2, [(0, 1, "OPT")]) == ["B-OPT", "O"]


def test_encode_decode_reversibility():
    spans = [(0, 5, "TITLE"), (6, 8, "OPT"), (9, 13, "TIME")]
    assert decode_bio(encode_bio(15, spans)) == spans


def test_two_consecutive_spans_wont_be_merged():
    spans = [(0, 2, "OPT"), (2, 4, "OPT")]
    assert decode_bio(encode_bio(4, spans)) == spans


def test_new_tag_means_new_span():
    tags = ["B-OPT", "I-OPT", "I-TIME", "I-TIME"]
    assert decode_bio(tags) == [(0, 2, "OPT"), (2, 4, "TIME")]


def test_convert_invalid_I_to_B():
    assert decode_bio(["I-OPT", "I-OPT", "O"]) == [(0, 2, "OPT")]


def test_not_accept_invalid_label():
    with pytest.raises(ValueError):
        encode_bio(3, [(0, 2, "NOT_A_LABEL")])
