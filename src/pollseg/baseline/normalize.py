_FULLWIDTH_TO_HALFWIDTH = str.maketrans(
    "０１２３４５６７８９：／，（）！？；｜＋－．　",
    "0123456789:/,()!?;|+-. ",
)

_PUNCT_ALIASES = str.maketrans(
    {
        "：": ":",
        "；": ";",
        "＿": "_",
        "～": "~",
        "－": "-",
        "–": "-",
        "—": "-",
    }
)


def normalize(text):
    normalized = text.translate(_FULLWIDTH_TO_HALFWIDTH).translate(_PUNCT_ALIASES)
    assert len(normalized) == len(text), "Length is different after normalization"
    return normalized
