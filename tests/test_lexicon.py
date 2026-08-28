import itertools

import pytest

from pollparse import lexicon
from pollparse.baseline.parser import parse
from pollparse.schema import LEXICON_LABELS

ALL_ENTRIES = [
    (label, surface, value)
    for label in LEXICON_LABELS
    for surface, value in lexicon.TABLES[label]
]


def test_every_label_in_lexicon():
    for label in LEXICON_LABELS:
        assert lexicon.TABLES.get(label), f"{label} not in lexicon"


@pytest.mark.parametrize(
    "label, surface, value",
    ALL_ENTRIES,
    ids=[f"{lab}:{s}" for lab, s, _ in ALL_ENTRIES],
)
def test_included_labels_are_lookupable(label, surface, value):
    assert lexicon.lookup(surface, label) == value


def test_return_non_on_unknown_label():
    assert lexicon.lookup("大家自己看著辦", "ANON") is None
    assert lexicon.lookup("匿名", "MULTI") is None


def test_same_word_doesnt_have_different_meaning():
    seen = {}
    for label, surface, value in ALL_ENTRIES:
        if surface in seen:
            assert seen[surface] == (label, value), (
                f"「{surface}」is both {seen[surface][0]} and {label}"
            )
        seen[surface] = (label, value)


def test_other_is_option_not_setting():
    assert lexicon.lookup("其他", "ADDOPT") is None
    result = parse("看哪部片？沙丘 芭比 其他")["target"]
    assert "其他" in result["options"]
    assert result["settings"]["allow_other"] is None


def test_resonable_limit_on_multichioce():
    assert parse("投票 A B C 最多選3個")["target"]["settings"]["max_choices"] == 3
    assert (
        parse("投票 A B C 每人99999999票")["target"]["settings"]["max_choices"] is None
    )


def _pairs():
    for (l1, t1), (l2, t2) in itertools.combinations(
        [(lab, lexicon.TABLES[lab]) for lab in LEXICON_LABELS], 2
    ):
        for (s1, v1), (s2, v2) in itertools.product(t1, t2):
            yield s1, v1, s2, v2


def test_consecutive_settings_are_parsable():
    failures = []
    for s1, v1, s2, v2 in _pairs():
        for text in (f"晚餐？A B {s1}{s2}", f"晚餐？A B {s2}{s1}"):
            settings = parse(text)["target"]["settings"]
            want = {**v1, **v2}
            if any(settings.get(k) != v for k, v in want.items()):
                failures.append(text)
    assert not failures, f"{len(failures)} not properly parsed, e.g. {failures[:5]}"


def test_time_survives_after_settings():
    failures = []
    times = ["九點截止", "晚上截止", "明天截止", "週五中午截止", "三點前投完"]
    for label, surface, value in ALL_ENTRIES:
        for time_text in times:
            settings = parse(f"晚餐？A B {time_text}{surface}")["target"]["settings"]
            if settings.get("deadline") is None:
                failures.append((time_text, surface, "Time missing"))
            elif any(settings.get(k) != v for k, v in value.items()):
                failures.append((time_text, surface, "Settings missing"))
    assert not failures, f"{len(failures)} not properly parsed, e.g. {failures[:5]}"
