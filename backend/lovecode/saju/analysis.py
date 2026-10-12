"""① 개인 원국 해석: 오행 분포, 일간 강약(억부), 조후, 용신 (팀 규약의 단순화 규칙).

유파: 자평명리 십성 체계, 억부 중심 + 조후 보조. 세부 가중치는 팀 규약이며 README에 공개한다.
"""
from __future__ import annotations

from .constants import (
    BRANCH_ELEMENT,
    CHAR_TEMP,
    ELEMENT_KO,
    HIDDEN_STEMS,
    POS_NAMES,
    SEASON,
    SEASON_TEMP,
    STEM_ELEMENT,
    STEM_YANG,
)
from .manse import Saju

# 강약 판단 가중치: 월지(득령) 3, 일지(득지) 2, 나머지 1
POS_WEIGHT_STEM = {"년": 1.0, "월": 1.0, "시": 1.0}
POS_WEIGHT_BRANCH = {"년": 1.0, "월": 3.0, "일": 2.0, "시": 1.0}
STRONG_TH, WEAK_TH = 0.47, 0.32  # 1970~2005년생 3,000명 분포로 신강·중화·신약이 대략 3등분되게 보정


def ten_god(day_stem: str, other_stem: str) -> str:
    me, ot = STEM_ELEMENT[day_stem], STEM_ELEMENT[other_stem]
    same = STEM_YANG[day_stem] == STEM_YANG[other_stem]
    diff = (ot - me) % 5
    names = {0: ("비견", "겁재"), 1: ("식신", "상관"), 2: ("편재", "정재"), 3: ("편관", "정관"), 4: ("편인", "정인")}
    return names[diff][0 if same else 1]


def family_element(day_stem: str, family: str) -> int:
    me = STEM_ELEMENT[day_stem]
    off = {"비겁": 0, "식상": 1, "재성": 2, "관성": 3, "인성": 4}[family]
    return (me + off) % 5


def element_family(day_stem: str, el: int) -> str:
    return {0: "비겁", 1: "식상", 2: "재성", 3: "관성", 4: "인성"}[(el - STEM_ELEMENT[day_stem]) % 5]


def _branch_elements(b: str) -> dict[int, float]:
    total = sum(dd for _, dd in HIDDEN_STEMS[b])
    out: dict[int, float] = {}
    for s, dd in HIDDEN_STEMS[b]:
        out[STEM_ELEMENT[s]] = out.get(STEM_ELEMENT[s], 0) + dd / total
    return out


def analyze_person(saju: Saju) -> dict:
    pillars = saju.pillars
    day_stem = saju.day[0]
    me = STEM_ELEMENT[day_stem]
    support = {me, (me - 1) % 5}  # 비겁, 인성

    chars = []  # (pos, kind, char)
    for pos, p in zip(POS_NAMES, pillars):
        if p is None:
            continue
        chars.append((pos, "간", p[0]))
        chars.append((pos, "지", p[1]))

    # 오행 분포: 겉글자 개수 + 지장간 비율 반영 가중치
    surface = [0] * 5
    weighted = [0.0] * 5
    for pos, kind, c in chars:
        if kind == "간":
            surface[STEM_ELEMENT[c]] += 1
            weighted[STEM_ELEMENT[c]] += 1.0
        else:
            surface[BRANCH_ELEMENT[c]] += 1
            for el, r in _branch_elements(c).items():
                weighted[el] += r

    # 강약
    num = den = 0.0
    for pos, kind, c in chars:
        if kind == "간":
            if pos == "일":
                continue
            w = POS_WEIGHT_STEM[pos]
            frac = 1.0 if STEM_ELEMENT[c] in support else 0.0
        else:
            w = POS_WEIGHT_BRANCH[pos]
            frac = sum(r for el, r in _branch_elements(c).items() if el in support)
        num += w * frac
        den += w
    score = num / den
    month_b, day_b = saju.month[1], saju.day[1]
    deukryeong = sum(r for el, r in _branch_elements(month_b).items() if el in support) >= 0.5
    deukji = sum(r for el, r in _branch_elements(day_b).items() if el in support) >= 0.5
    strength = "신강" if score >= STRONG_TH else ("신약" if score <= WEAK_TH else "중화")

    # 조후
    season = SEASON[month_b]
    temp = SEASON_TEMP[season] + sum(CHAR_TEMP.get(c, 0) for _, _, c in chars)
    climate = "차가움" if temp <= -2.5 else ("뜨거움" if temp >= 2.5 else "온화")

    # 억부 용신
    fam_w = {f: weighted[family_element(day_stem, f)] for f in ["비겁", "식상", "재성", "관성", "인성"]}
    if strength == "신약":
        drain = max(["식상", "재성", "관성"], key=lambda f: fam_w[f])
        yong_f, hee_f = ("비겁", "인성") if drain == "재성" else ("인성", "비겁")
        gi_f = drain
    elif strength == "신강":
        if fam_w["인성"] > fam_w["비겁"]:
            yong_f, hee_f, gi_f = "재성", "식상", "인성"
        else:
            yong_f, hee_f, gi_f = ("관성", "재성", "비겁") if fam_w["관성"] >= 0.8 else ("식상", "재성", "비겁")
    else:
        lo = min(range(5), key=lambda e: weighted[e])
        hi = max(range(5), key=lambda e: weighted[e])
        yong_f, hee_f, gi_f = element_family(day_stem, lo), None, element_family(day_stem, hi)

    yong = family_element(day_stem, yong_f)
    hee = family_element(day_stem, hee_f) if hee_f else None
    gi = family_element(day_stem, gi_f)
    johu = 1 if climate == "차가움" else (4 if climate == "뜨거움" else None)
    # 조후 용신이 기신과 겹치면 조후를 우선하고 기신 표기는 유지하지 않는다
    if johu is not None and johu == gi:
        gi = None

    ten_gods = {}
    for pos, p in zip(POS_NAMES, pillars):
        if p is None or pos == "일":
            continue
        ten_gods[f"{pos}간"] = ten_god(day_stem, p[0])

    return {
        "day_stem": day_stem,
        "day_element": me,
        "surface": surface,
        "weighted": [round(x, 2) for x in weighted],
        "strength": strength,
        "strength_score": round(score, 3),
        "deukryeong": deukryeong,
        "deukji": deukji,
        "season": season,
        "temp": temp,
        "climate": climate,
        "yong": yong, "hee": hee, "gi": gi, "johu": johu,
        "yong_family": yong_f, "gi_family": gi_f,
        "needs": sorted({e for e in [yong, hee, johu] if e is not None}),
        "lacking": [e for e in range(5) if surface[e] == 0],
        "ten_gods": ten_gods,
    }


def element_name(e: int) -> str:
    return ELEMENT_KO[e]
