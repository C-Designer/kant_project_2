"""매운맛 궁합: 신호 + 유형 축 → 주제별 고정 칭호 (docs/SPICY_SPEC.md §2).

칭호는 규칙이 고르고 LLM은 설명만 쓴다. 규칙은 위에서부터 처음 맞는 것을 쓴다.
"""

import re
from itertools import product

TOPICS = ("skinship", "temptation", "jealousy", "reunion")
SIGNALS = ("doha", "hongyeom", "day_bond", "day_clash")

TITLES = {
    "S1": "눈만 마주쳐도 분위기 ㅈㄴ 이상해지는 커플",
    "S2": "시동은 같이 거는데 엔진 식는 속도가 다른 커플",
    "S3": "겉은 얌전, 불 끄면 온도 급상승 커플",
    "S4": "진도 빼는 데 n개월 걸리는 신중 끝판왕 커플",
    "C1": "DM 알림 뜰 때마다 서로 째려보는 커플",
    "C2": "밖에선 인기 폭발, 집에선 감시 모드 커플",
    "C3": "한눈팔 시간에 잠이나 자는 귀차니즘 커플",
    "C4": "남들은 전부 NPC로 보이는 커플",
    "J1": "읽씹 30초면 부재중 3통 커플",
    "J2": "팔로잉 목록 정기 점검하는 커플",
    "J3": "쿨병 걸렸다가 새벽 2시에 폭발하는 커플",
    "J4": "서로 안 궁금해서 오히려 불안한 커플",
    "R1": "헤어지고 3일 만에 '자니?' 보내는 커플",
    "R2": "이별 통보하고 1시간 뒤 '밥은 먹었어?' 커플",
    "R3": "차단했다 풀었다 무한 반복 커플",
    "R4": "헤어지면 연락처부터 지우는 칼 같은 커플",
}

# (조건, 칭호 ID). f = 신호 + 축 플래그(passionate, together, immediate).
RULES = {
    "skinship": [
        (lambda f: f["passionate"] and (f["day_bond"] or f["hongyeom"]), "S1"),
        (lambda f: f["passionate"], "S2"),
        (lambda f: f["day_bond"] or f["hongyeom"], "S3"),
        (lambda f: True, "S4"),
    ],
    "temptation": [
        (lambda f: f["doha"] and not f["together"], "C1"),
        (lambda f: f["doha"], "C2"),
        (lambda f: not f["together"], "C3"),
        (lambda f: True, "C4"),
    ],
    "jealousy": [
        (lambda f: f["together"] and f["passionate"], "J1"),
        (lambda f: f["together"], "J2"),
        (lambda f: f["day_clash"], "J3"),
        (lambda f: True, "J4"),
    ],
    "reunion": [
        (lambda f: f["day_bond"] and not f["immediate"], "R1"),
        (lambda f: f["day_bond"], "R2"),
        (lambda f: f["day_clash"] and f["immediate"], "R3"),
        (lambda f: True, "R4"),
    ],
}


def _flags(signals, type_id):
    from .contracts import TAXONOMY  # contracts imports this module for its checks

    axes = TAXONOMY[type_id]["axes"]
    return {
        **{k: bool(signals[k]) for k in SIGNALS},
        "passionate": axes["temperature"] == "passionate",
        "together": axes["distance"] == "together",
        "immediate": axes["conflict"] == "immediate",
    }


def pick_titles(signals, type_id):
    """{topic: {"id", "text"}} — 같은 신호와 유형이면 항상 같은 칭호."""
    f = _flags(signals, type_id)
    out = {}
    for topic in TOPICS:
        title_id = next(tid for cond, tid in RULES[topic] if cond(f))
        out[topic] = {"id": title_id, "text": TITLES[title_id]}
    return out


def reachable_titles(type_id):
    """유형만 알 때 나올 수 있는 칭호 ID (/types 상세용). 신호 16조합을 모두 대입한다."""
    out = {t: [] for t in TOPICS}
    for values in product((False, True), repeat=len(SIGNALS)):
        for topic, title in pick_titles(dict(zip(SIGNALS, values)), type_id).items():
            if title["id"] not in out[topic]:
                out[topic].append(title["id"])
    return {t: sorted(ids) for t, ids in out.items()}


# 매운맛 문구 검사 (§2.4). 주제어(속궁합·바람기)는 허용하고 아래만 막는다.
# 초성·순화 표현(ㅈㄴ, 개-, 미쳤다)은 허용, 원형 욕설은 금지.
EXPLICIT_RE = re.compile(
    r"섹스|성관계|성행위|잠자리|체위|오르가즘|성기|알몸|나체|야동|애무|삽입|사정|발기|모텔"
)
PROFANITY_RE = re.compile(r"씨발|시발|씨팔|ㅅㅂ|개새|새끼|병신|ㅂㅅ|좆|존나|졸라|지랄|닥쳐|꺼져")
CERTAINTY_RE = re.compile(r"\d+\s*%|퍼센트|확률|등급|반드시|무조건|운명|100\s*프로")
COMMON_RE = re.compile(
    r"https?://|[<>]|[EI][SN][TF][JP]|\d{2,4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}:\d{2}"
    r"|[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]"
)


NOTE_MAX = 140
TITLE_MAX = 40


def spicy_text_ok(text, max_len=NOTE_MAX):
    return 1 <= len(text) <= max_len and not any(
        r.search(text) for r in (EXPLICIT_RE, PROFANITY_RE, CERTAINTY_RE, COMMON_RE)
    )
