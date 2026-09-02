import re

from .numerals import to_int

Entry = tuple[str, dict]

# a full list of lexicon for lookup.
MULTI_YES_PREFIXES = ["可", "可以", "能", ""]
MULTI_YES_STEMS = [
    "複選",
    "多選",
    "重複選",
    "選多個",
    "選很多個",
    "選好幾個",
    "選多項",
    "勾多項",
    "勾多個",
]

MULTI_YES_EXTRA = ["複選題", "可以都選", "都可以選", "可複", "可多", "都選", "全選"]

MULTI_NO_ENTRIES = [
    "單選",
    "單選題",
    "只能選一個",
    "只能選一項",
    "只能一個",
    "只能一項",
    "限選一個",
    "限選一項",
    "一人一票",
    "每人一票",
    "不能複選",
    "不能多選",
    "不可複選",
    "不能重複選",
    "只可以選一個",
    "只能勾一個",
]

MULTI: list[Entry] = (
    [
        (prefix + stem, {"multichoice": True})
        for stem in MULTI_YES_STEMS
        for prefix in MULTI_YES_PREFIXES
    ]
    + [(word, {"multichoice": True}) for word in MULTI_YES_EXTRA]
    + [(word, {"multichoice": False}) for word in MULTI_NO_ENTRIES]
)

MULTI_LIMIT_TEMPLATES = [
    "最多選{n}個",
    "最多選{n}項",
    "最多{n}個",
    "最多{n}項",
    "最多可選{n}個",
    "最多可選{n}項",
    "限選{n}個",
    "限選{n}項",
    "只能選{n}個",
    "只能選{n}項",
    "可以選{n}個",
    "可以選{n}項",
    "可選{n}個",
    "可選{n}項",
    "選{n}個",
    "選{n}項",
    "至多{n}個",
    "至多選{n}個",
    "勾{n}個",
    "最多勾{n}個",
    "可勾{n}個",
    "{n}個以內",
    "{n}項以內",
    "限{n}個",
    "限{n}項",
    "只能{n}個",
    "只能{n}項",
    "每人{n}票",
    "一人{n}票",
    "每人最多{n}票",
    "一人最多{n}票",
    "每人限{n}票",
    "一人限{n}票",
    "每人限投{n}票",
    "一人限投{n}票",
    "每人可投{n}票",
    "每人有{n}票",
]

_NUM = r"(\d{1,4}|[一兩二三四五六七八九十]+)"

LIMIT_PATTERN = "|".join(
    "(?:" + re.escape(template).replace(re.escape("{n}"), _NUM) + ")"
    for template in MULTI_LIMIT_TEMPLATES
)
_LIMIT_RE = re.compile(LIMIT_PATTERN)

ANON: list[Entry] = [
    ("匿名", {"anonymous": True}),
    ("匿名投票", {"anonymous": True}),
    ("不記名", {"anonymous": True}),
    ("不記名投票", {"anonymous": True}),
    ("秘密投票", {"anonymous": True}),
    ("不公開投票人", {"anonymous": True}),
    ("不顯示投票人", {"anonymous": True}),
    ("記名", {"anonymous": False}),
    ("記名投票", {"anonymous": False}),
    ("不匿名", {"anonymous": False}),
    ("公開投票", {"anonymous": False}),
    ("實名制", {"anonymous": False}),
    ("顯示投票人", {"anonymous": False}),
]

HOST_ROLES = ["房主", "主揪", "發起人", "主持人", "開房的", "主辦", "開這個的人", "我"]
HOST_NO_TEMPLATES = [
    "{r}不投",
    "{r}不投票",
    "{r}不參與",
    "{r}不算",
    "{r}不能投",
]
HOST_YES_TEMPLATES = [
    "{r}也投",
    "{r}也要投",
    "{r}可投",
    "{r}要投",
    "{r}一起投",
    "{r}可以投票",
]


HOST: list[Entry] = [
    (template.format(r=role), {"host_can_vote": can_vote})
    for can_vote, templates in ((False, HOST_NO_TEMPLATES), (True, HOST_YES_TEMPLATES))
    for template in templates
    for role in HOST_ROLES
]

LIVE_ADVERBS = ["即時", "立即", "馬上", "立刻", "當場"]
LIVE_ACTIONS = ["開票", "計票", "公布", "開獎"]

LIVE_WATCH_ADVERBS = ["即時", "隨時", "馬上", "立刻"]
LIVE_WATCH_ACTIONS = ["看票數", "顯示票數", "更新票數", "查看票數"]

LIVE_LATE_PREFIXES = ["投完才", "最後才", "都投完才", "大家投完才", "全部投完才"]
LIVE_LATE_ACTIONS = ["公布", "開票", "計票"]

LIVE_YES_EXTRA = [
    "邊投邊看",
    "邊投邊開",
    "投完就看得到",
    "投完可以看票數",
    "隨時可以看票數",
    "公開票數",
    "開放看票數",
]
LIVE_NO_EXTRA = ["不公開票數", "最後公布票數", "先不要公布票數", "先不公布"]

LIVE: list[Entry] = (
    [
        (adverb + action, {"live_results": True})
        for action in LIVE_ACTIONS
        for adverb in LIVE_ADVERBS
    ]
    + [
        (adverb + action, {"live_results": True})
        for action in LIVE_WATCH_ACTIONS
        for adverb in LIVE_WATCH_ADVERBS
    ]
    + [(word, {"live_results": True}) for word in LIVE_YES_EXTRA]
    + [
        ("不" + adverb + action, {"live_results": False})
        for action in LIVE_ACTIONS
        for adverb in LIVE_ADVERBS
    ]
    + [
        (prefix + action, {"live_results": False})
        for action in LIVE_LATE_ACTIONS
        for prefix in LIVE_LATE_PREFIXES
    ]
    + [(word, {"live_results": False}) for word in LIVE_NO_EXTRA]
)
ADDOPT_YES_PREFIXES = ["可", "可以", "開放", "允許"]
ADDOPT_NO_PREFIXES = ["不能", "不可", "不開放"]
ADDOPT_STEMS = [
    "新增",
    "新增選項",
    "加選項",
    "補選項",
    "自己加",
    "自己填",
    "自己寫",
    "自訂",
    "自訂選項",
    "自由填寫",
]

ADDOPT: list[Entry] = (
    [
        (prefix + stem, {"allow_other": True})
        for stem in ADDOPT_STEMS
        for prefix in ADDOPT_YES_PREFIXES
    ]
    + [
        (prefix + stem, {"allow_other": False})
        for stem in ADDOPT_STEMS
        for prefix in ADDOPT_NO_PREFIXES
    ]
    + [
        (word, {"allow_other": False})
        for word in ["只能選現有的", "只能選上面的", "不能加"]
    ]
)
TABLES: dict[str, list[Entry]] = {
    "MULTI": MULTI,
    "ANON": ANON,
    "HOST": HOST,
    "LIVE": LIVE,
    "ADDOPT": ADDOPT,
}


def surfaces(label: str) -> list[str]:
    return [surface for surface, _ in TABLES[label]]


def lookup(text, label):
    table = TABLES.get(label)
    if table is None:
        return None
    for surface, value in table:
        if surface == text:
            return dict(value)
    if label == "MULTI":
        match = _LIMIT_RE.fullmatch(text)
        if match:
            captured = next(group for group in match.groups() if group)
            limit = to_int(captured)
            if limit:
                return {"multichoice": limit > 1, "max_choices": limit}
    return None
