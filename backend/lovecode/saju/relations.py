"""① 두 사람 사이의 관계 목록 (사실 계산 + 맥락 태그).

판정(16유형)은 하지 않는다. 판정은 분류 모델의 몫이다.
"""
from __future__ import annotations

import math
from itertools import product

from .analysis import ten_god
from .constants import (BRANCH_CLASH, BRANCH_ELEMENT, BRANCH_HARM, BRANCH_PUNISH, BRANCH_SIX_COMBINE,
                        BRANCH_WONJIN, DIRECTION_COMBINE, MAIN_HIDDEN, POS_NAMES, SELF_PUNISH,
                        STEM_CLASH, STEM_COMBINE, STEM_ELEMENT, TRIPLE_COMBINE, MBTI_AXES)

# 위치 중요도 (판단 기준 문서의 우선순위와 같다)
POS_RANK = {("일", "일"): 3, ("월", "월"): 2, ("일", "월"): 2, ("월", "일"): 2}


def _rank(pa: str, pb: str) -> int:
    return POS_RANK.get((pa, pb), 1)


def _effect_on(person: dict, element: int) -> str | None:
    """어떤 오행이 그 사람에게 어떤 의미인지."""
    if element == person["yong"] or element == person.get("johu"):
        return "용신"
    if person.get("hee") is not None and element == person["hee"]:
        return "희신"
    if person.get("gi") is not None and element == person["gi"]:
        return "기신"
    return None


def _clash_tags(a: dict, b: dict, ca: str, cb: str, is_stem: bool) -> list[str]:
    """충·형·해·원진에서 '누가 무엇을 치는가' 태그. ca는 A의 글자, cb는 B의 글자."""
    el = STEM_ELEMENT if is_stem else BRANCH_ELEMENT
    tags = []
    for who, person, hit in (("A", a, ca), ("B", b, cb)):
        eff = _effect_on(person, el[hit])
        if eff == "기신":
            tags.append(f"{who}의 기신({hit})을 눌러 줌")
        elif eff in ("용신", "희신"):
            tags.append(f"{who}에게 필요한 기운({hit})을 막음")
    return tags


def _combine_tags(a: dict, b: dict, hua: int) -> list[str]:
    tags = []
    for who, person in (("A", a), ("B", b)):
        eff = _effect_on(person, hua)
        if eff in ("용신", "희신"):
            tags.append(f"합의 기운이 {who}에게 도움")
        elif eff == "기신":
            tags.append(f"합의 기운이 {who}에게 부담")
    return tags


def _pillar_chars(saju: dict, idx: int) -> list[tuple[str, str]]:
    out = []
    for pos, p in zip(POS_NAMES, saju["pillars"]):
        if p is not None:
            out.append((pos, p[idx]))
    return out


def spouse_info(me: dict, me_saju: dict, gender: str, partner_saju: dict) -> dict:
    tg = ten_god(me_saju["day"][0], partner_saju["day"][0])
    if gender not in ("M", "F"):
        return {"partner_day_stem_ten_god": tg, "is_spouse_star": False, "is_main_spouse_star": False}
    target = ("정재", "편재") if gender == "M" else ("정관", "편관")
    return {"partner_day_stem_ten_god": tg, "is_spouse_star": tg in target, "is_main_spouse_star": tg == target[0]}


def mbti_compare(ma: str, mb: str) -> dict:
    same = [x for x in ma if x in mb]
    return {"same": same, "same_count": len(same),
            "diff": [f"{ma[i]}/{mb[i]}" for i in range(4) if ma[i] != mb[i]]}


def analyze_pair(A: dict, B: dict) -> dict:
    """A, B: {'gender','mbti','saju': Saju.to_dict(), 'analysis': analyze_person()}"""
    sa, sb, a, b = A["saju"], B["saju"], A["analysis"], B["analysis"]
    rels: list[dict] = []

    # 천간
    for (pa, ca), (pb, cb) in product(_pillar_chars(sa, 0), _pillar_chars(sb, 0)):
        key = frozenset((ca, cb))
        if key in STEM_COMBINE and ca != cb:
            hua = STEM_COMBINE[key]
            rels.append({"type": "천간합", "a": f"{pa}간 {ca}", "b": f"{pb}간 {cb}", "rank": _rank(pa, pb) + (1 if pa == pb == "일" else 0),
                         "hua": hua, "tags": _combine_tags(a, b, hua)})
        elif key in STEM_CLASH:
            rels.append({"type": "천간충", "a": f"{pa}간 {ca}", "b": f"{pb}간 {cb}", "rank": _rank(pa, pb) + (1 if pa == pb == "일" else 0),
                         "tags": _clash_tags(a, b, ca, cb, True)})

    # 지지 (두 글자)
    for (pa, ca), (pb, cb) in product(_pillar_chars(sa, 1), _pillar_chars(sb, 1)):
        key = frozenset((ca, cb))
        base = {"a": f"{pa}지 {ca}", "b": f"{pb}지 {cb}", "rank": _rank(pa, pb)}
        if key in BRANCH_SIX_COMBINE and ca != cb:
            hua = BRANCH_SIX_COMBINE[key]
            rels.append({"type": "육합", **base, "hua": hua, "tags": _combine_tags(a, b, hua)})
        for chars, hua in TRIPLE_COMBINE:
            if ca != cb and ca in chars and cb in chars and chars[1] in (ca, cb):
                rels.append({"type": "반합", **base, "hua": hua, "tags": _combine_tags(a, b, hua)})
        # 충은 드러나는 갈등, 원진·해·형은 숨은 갈등으로 따로 둔다. 같은 글자 쌍의 원진·해·형은 한 줄로 합친다.
        if key in BRANCH_CLASH:
            rels.append({"type": "충", **base, "tags": _clash_tags(a, b, ca, cb, False)})
        hidden = [n for n, tbl in (("원진", BRANCH_WONJIN), ("해", BRANCH_HARM), ("형", BRANCH_PUNISH))
                  if key in tbl and ca != cb]
        if hidden:
            rels.append({"type": "·".join(hidden), **base, "tags": _clash_tags(a, b, ca, cb, False)})

    # 일지 암합 (정기끼리 천간합)
    da, db = sa["day"][1], sb["day"][1]
    hk = frozenset((MAIN_HIDDEN[da], MAIN_HIDDEN[db]))
    if hk in STEM_COMBINE and MAIN_HIDDEN[da] != MAIN_HIDDEN[db]:
        rels.append({"type": "암합", "a": f"일지 {da}", "b": f"일지 {db}", "rank": 3, "hua": STEM_COMBINE[hk],
                     "tags": _combine_tags(a, b, STEM_COMBINE[hk])})

    # 두 사람이 함께 만드는 삼합·방합 (각자 1글자 이상 기여)
    ba = {c for _, c in _pillar_chars(sa, 1)}
    bb = {c for _, c in _pillar_chars(sb, 1)}
    for kind, table in (("삼합", TRIPLE_COMBINE), ("방합", DIRECTION_COMBINE)):
        for chars, hua in table:
            s = set(chars)
            if s <= (ba | bb) and (ba & s) and (bb & s) and not s <= ba and not s <= bb:
                rels.append({"type": kind, "a": "".join(sorted(ba & s, key=chars.index)),
                             "b": "".join(sorted(bb & s, key=chars.index)), "rank": 2, "hua": hua,
                             "chars": chars, "tags": _combine_tags(a, b, hua)})

    # 용신 보완: 상대가 내게 필요한 기운을 얼마나 가졌나 (가중 오행 비율)
    def supply(receiver: dict, giver: dict) -> dict:
        tot = sum(giver["weighted"])
        share = sum(giver["weighted"][e] for e in receiver["needs"]) / tot
        level = "많음" if share >= 0.40 else ("보통" if share >= 0.22 else "적음")
        return {"share": round(share, 3), "level": level}

    va, vb = a["weighted"], b["weighted"]
    cos = sum(x * y for x, y in zip(va, vb)) / (math.sqrt(sum(x * x for x in va)) * math.sqrt(sum(y * y for y in vb)))

    combined_temp = a["temp"] + b["temp"]
    combined_climate = "차가움" if combined_temp <= -3 else ("뜨거움" if combined_temp >= 3 else "균형")

    return {
        "relations": sorted(rels, key=lambda r: -r["rank"]),
        "supply_b_to_a": supply(a, b),
        "supply_a_to_b": supply(b, a),
        "element_similarity": round(cos, 3),
        "same_day_element": a["day_element"] == b["day_element"],
        "same_season": a["season"] == b["season"],
        "opposite_climate": {a["climate"], b["climate"]} == {"차가움", "뜨거움"},
        "combined_temp": combined_temp,
        "combined_climate": combined_climate,
        "spouse_a": spouse_info(a, sa, A["gender"], sb),
        "spouse_b": spouse_info(b, sb, B["gender"], sa),
        "a_sees_b": ten_god(sa["day"][0], sb["day"][0]),
        "b_sees_a": ten_god(sb["day"][0], sa["day"][0]),
        "mbti": mbti_compare(A["mbti"], B["mbti"]),
    }
