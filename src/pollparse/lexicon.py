import re

from .numerals import to_int

Entry = tuple[str, dict]

MULTI: list[Entry] = [
    ("可複選", {"multichoice": True}),
    ("複選", {"multichoice": True}),
    ("複選題", {"multichoice": True}),
    ("可多選", {"multichoice": True}),
    ("可以多選", {"multichoice": True}),
    ("多選", {"multichoice": True}),
    ("可以都選", {"multichoice": True}),
    ("可勾多項", {"multichoice": True}),
    ("單選", {"multichoice": False}),
    ("單選題", {"multichoice": False}),
    ("只能選一個", {"multichoice": False}),
    ("只能選一項", {"multichoice": False}),
    ("限選一個", {"multichoice": False}),
    ("限選一項", {"multichoice": False}),
    ("一人一票", {"multichoice": False}),
    ("每人一票", {"multichoice": False}),
    ("不能複選", {"multichoice": False}),
    ("不能多選", {"multichoice": False}),
]

MULTI_LIMIT_TEMPLATES = [
    "最多選{n}個",
    "最多選{n}項",
    "最多{n}個",
    "限選{n}個",
    "每人{n}票",
]

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

HOST_ROLES = ["房主", "主揪", "發起人", "主持人", "開房的", "我"]
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

LIVE: list[Entry] = [
    ("即時開票", {"live_results": True}),
    ("即時計票", {"live_results": True}),
    ("即時公布", {"live_results": True}),
    ("即時開獎", {"live_results": True}),
    ("即時顯示票數", {"live_results": True}),
    ("即時看票數", {"live_results": True}),
    ("邊投邊看", {"live_results": True}),
    ("邊投邊開", {"live_results": True}),
    ("投完就看得到", {"live_results": True}),
    ("投完可以看票數", {"live_results": True}),
    ("隨時看票數", {"live_results": True}),
    ("隨時可以看票數", {"live_results": True}),
    ("隨時查看票數", {"live_results": True}),
    ("即時更新票數", {"live_results": True}),
    ("公開票數", {"live_results": True}),
    ("開放看票數", {"live_results": True}),
    ("不即時開票", {"live_results": False}),
    ("不即時計票", {"live_results": False}),
    ("不即時公布", {"live_results": False}),
    ("投完才公布", {"live_results": False}),
    ("投完才開票", {"live_results": False}),
    ("最後才開票", {"live_results": False}),
    ("最後才公布", {"live_results": False}),
    ("全部投完才公布", {"live_results": False}),
    ("不公開票數", {"live_results": False}),
    ("最後公布票數", {"live_results": False}),
    ("大家投完才公布", {"live_results": False}),
    ("都投完才公布", {"live_results": False}),
    ("先不要公布票數", {"live_results": False}),
]

TABLES: dict[str, list[Entry]] = {
    "MULTI": MULTI,
    "ANON": ANON,
    "HOST": HOST,
    "LIVE": LIVE,
}

_NUM = r"(\d+|[一兩二三四五六七八九十]+)"

LIMIT_PATTERN = "|".join(
    "(?:" + re.escape(template).replace(re.escape("{n}"), _NUM) + ")"
    for template in MULTI_LIMIT_TEMPLATES
)
_LIMIT_RE = re.compile(LIMIT_PATTERN)


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
