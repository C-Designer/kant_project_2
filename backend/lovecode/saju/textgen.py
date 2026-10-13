"""② 텍스트 변환 (규칙).

같은 사실을 여러 템플릿·표현·순서로 서술해, 분류 모델이 고정 문장 패턴만 외우지 않게 한다.
- make_text(): 분류 모델 입력 (템플릿 4종 x 표기 3종 x 문장 순서 무작위)
- make_label_view(): 라벨러(사람/LLM)용 고정 형식 요약 (근거를 빠짐없이 표시)
"""
from __future__ import annotations

import random

from .constants import BRANCH_KO, ELEMENT_KO, ELEMENT_PLAIN, STEM_ELEMENT, STEM_KO

GENDER_KO = {"M": "남", "F": "여"}


def _who(tag: str, P: dict) -> str:
    g = GENDER_KO.get(P["gender"])
    return f"{tag}({g})" if g else tag


def _stem(c: str, style: int) -> str:
    el = ELEMENT_KO[STEM_ELEMENT[c]]
    from .constants import ELEMENTS
    if style == 0:
        return f"{STEM_KO[c]}{el}({c}{ELEMENTS[STEM_ELEMENT[c]]})"
    if style == 1:
        return f"{STEM_KO[c]}{el}"
    return f"{c}{ELEMENTS[STEM_ELEMENT[c]]}"


def _char(c: str, style: int) -> str:
    ko = STEM_KO.get(c) or BRANCH_KO.get(c)
    return f"{ko}({c})" if style == 0 else (ko if style == 1 else c)


def _el(e: int, rnd: random.Random) -> str:
    return rnd.choice([ELEMENT_KO[e], ELEMENT_PLAIN[e], f"{ELEMENT_PLAIN[e]}({ELEMENT_KO[e]})"])


def _els(es: list[int], rnd: random.Random) -> str:
    return "·".join(_el(e, rnd) for e in es) if es else "없음"


def _pos_text(s: str, style: int) -> str:
    # "일간 丙" -> "일간 병"
    pos, c = s.split(" ") if " " in s else ("", s)
    chars = "".join(_char(x, style) for x in c)
    return f"{pos} {chars}".strip()


def _person_sentences(tag: str, P: dict, rnd: random.Random, style: int) -> list[str]:
    s, a = P["saju"], P["analysis"]
    out = []
    ds = _stem(a["day_stem"], style)
    strength_words = {"신강": rnd.choice(["신강", "기운이 강한 편", "일간이 강함"]),
                      "신약": rnd.choice(["신약", "기운이 약한 편", "일간이 약함"]),
                      "중화": rnd.choice(["중화", "강약이 균형", "강하지도 약하지도 않음"])}[a["strength"]]
    climate_words = {"차가움": rnd.choice(["차갑고 습한 사주", "차가운 편", "온기가 부족함"]),
                     "뜨거움": rnd.choice(["뜨겁고 건조한 사주", "뜨거운 편", "열기가 많음"]),
                     "온화": rnd.choice(["온도가 무난함", "온화한 편", "춥지도 덥지도 않음"])}[a["climate"]]
    out.append(f"{_who(tag, P)}는 {a['season']}생이고 일간은 {ds}입니다.")
    out.append(rnd.choice([f"{tag}는 {strength_words}이며 {climate_words}입니다.",
                           f"{tag}의 원국: {strength_words}, {climate_words}.",
                           f"{tag}는 {climate_words}이고 {strength_words}입니다."]))
    out.append(rnd.choice([f"{tag}에게 필요한 기운은 {_els(a['needs'], rnd)}입니다.",
                           f"{tag}의 용신 쪽 기운: {_els(a['needs'], rnd)}.",
                           f"{tag}는 {_els(a['needs'], rnd)} 기운이 들어오면 좋습니다."]))
    if a.get("gi") is not None:
        out.append(rnd.choice([f"{tag}에게 부담이 되는 기운은 {_el(a['gi'], rnd)}입니다.",
                               f"{tag}의 기신은 {_el(a['gi'], rnd)}입니다."]))
    if a["lacking"]:
        out.append(rnd.choice([f"{tag}의 팔자에는 {_els(a['lacking'], rnd)} 기운이 없습니다.",
                               f"{tag}는 {_els(a['lacking'], rnd)}이(가) 비어 있습니다."]))
    if not s["time_known"]:
        out.append(rnd.choice([f"{tag}는 생시를 몰라 시주를 제외했습니다.", f"{tag}는 태어난 시각 미상(시주 제외)."]))
    out.append(rnd.choice([f"{tag}의 MBTI는 {P['mbti']}입니다.", f"{tag} MBTI {P['mbti']}.", f"MBTI는 {tag}가 {P['mbti']}."]))
    return out


REL_PHRASE = {
    "천간합": ["{a}와 {b}가 천간합을 이룹니다", "{a}·{b} 천간합", "{a}과 {b}이 서로 합합니다"],
    "천간충": ["{a}와 {b}가 천간충입니다", "{a}·{b} 천간끼리 부딪침(충)", "{a}과 {b}이 충돌합니다"],
    "육합": ["{a}와 {b}가 육합입니다", "{a}·{b} 육합", "{a}과 {b}이 짝을 이룹니다(육합)"],
    "반합": ["{a}와 {b}가 반합입니다", "{a}·{b} 반합", "{a}과 {b}이 반쯤 합을 이룹니다"],
    "충": ["{a}와 {b}가 충입니다", "{a}·{b} 충", "{a}과 {b}이 정면으로 부딪칩니다(충)"],
    "원진": ["{a}와 {b}가 원진입니다", "{a}·{b} 원진", "{a}과 {b} 사이에 원진이 있습니다"],
    "해": ["{a}와 {b}가 해(害)입니다", "{a}·{b} 해", "{a}과 {b}이 서로 해칩니다(해)"],
    "형": ["{a}와 {b}가 형입니다", "{a}·{b} 형", "{a}과 {b} 사이에 형이 있습니다"],
    "암합": ["{a}와 {b}가 암합입니다", "{a}·{b} 속으로 합함(암합)", "{a}과 {b}이 겉으로 드러나지 않게 합합니다"],
    "삼합": ["두 사람의 지지가 함께 삼합({chars})을 이룹니다", "삼합 {chars} 성립(두 사람 합작)"],
    "방합": ["두 사람의 지지가 함께 방합({chars})을 이룹니다", "방합 {chars} 성립(두 사람 합작)"],
}


def _rel_sentence(r: dict, rnd: random.Random, style: int) -> str:
    if r["type"] in ("삼합", "방합"):
        chars = "".join(_char(c, style) for c in r["chars"])
        base = rnd.choice(REL_PHRASE[r["type"]]).format(chars=chars)
    else:
        a = "A " + _pos_text(r["a"], style)
        b = "B " + _pos_text(r["b"], style)
        phrases = REL_PHRASE.get(r["type"]) or ["{a}와 {b} 사이에 " + r["type"] + "이(가) 있습니다",
                                                  "{a}·{b} " + r["type"],
                                                  "{a}과 {b}이 " + r["type"] + " 관계입니다"]
        base = rnd.choice(phrases).format(a=a, b=b)
    extra = []
    if "hua" in r:
        extra.append(rnd.choice([f"합하면 {_el(r['hua'], rnd)} 기운", f"{_el(r['hua'], rnd)} 기운으로 변함"]))
    extra += r.get("tags", [])
    return base + (f" ({', '.join(extra)})" if extra else "") + "."


def _summary_sentences(F: dict, rnd: random.Random) -> list[str]:
    out = []
    lvl = {"많음": rnd.choice(["많이", "넉넉히"]), "보통": rnd.choice(["어느 정도", "보통 수준으로"]), "적음": rnd.choice(["조금만", "거의 못"])}
    out.append(f"B는 A에게 필요한 기운을 {lvl[F['supply_b_to_a']['level']]} 채워 줍니다.")
    out.append(f"A는 B에게 필요한 기운을 {lvl[F['supply_a_to_b']['level']]} 채워 줍니다.")
    sim = F["element_similarity"]
    out.append(rnd.choice([
        "두 사람의 오행 분포는 " + ("매우 비슷합니다." if sim >= 0.85 else "어느 정도 비슷합니다." if sim >= 0.65 else "많이 다릅니다."),
        "오행 구성 유사도: " + ("높음." if sim >= 0.85 else "중간." if sim >= 0.65 else "낮음."),
    ]))
    if F["opposite_climate"]:
        out.append(rnd.choice(["한 사람은 차갑고 한 사람은 뜨거워 온도가 정반대입니다.", "두 사람의 사주 온도가 정반대입니다."]))
    out.append(rnd.choice([
        f"둘을 합치면 사주 온도는 {F['combined_climate']}입니다.",
        f"합친 기운의 온도: {F['combined_climate']}.",
    ]))
    if F["same_day_element"]:
        out.append("두 사람의 일간 오행이 같습니다.")
    if F["same_season"]:
        out.append("두 사람은 같은 계절에 태어났습니다.")
    sa, sb = F["spouse_a"], F["spouse_b"]
    out.append(f"A에게 B의 일간은 {F['a_sees_b']}" + (" (배우자를 뜻하는 글자)" if sa["is_spouse_star"] else "") + "입니다.")
    out.append(f"B에게 A의 일간은 {F['b_sees_a']}" + (" (배우자를 뜻하는 글자)" if sb["is_spouse_star"] else "") + "입니다.")
    m = F["mbti"]
    out.append(rnd.choice([
        f"MBTI는 {''.join(m['same']) or '없음'}이(가) 같고, " + (", ".join(m["diff"]) + "이(가) 다릅니다." if m["diff"] else "모두 같습니다."),
        f"MBTI 일치 글자 {m['same_count']}개" + (f", 차이 {', '.join(m['diff'])}." if m["diff"] else "."),
    ]))
    return out


def make_text(A: dict, B: dict, F: dict, seed: int, max_rel: int = 7) -> tuple[str, int]:
    rnd = random.Random(seed)
    template = rnd.randrange(4)
    style = rnd.randrange(3)
    pa = _person_sentences("A", A, rnd, style)
    pb = _person_sentences("B", B, rnd, style)
    rels = F["relations"][:max_rel]
    rel_s = [_rel_sentence(r, rnd, style) for r in rels] or ["두 사람 사이에 뚜렷한 합이나 충은 없습니다."]
    summ = _summary_sentences(F, rnd)
    if template != 0:
        rnd.shuffle(rel_s)
        rnd.shuffle(summ)
    if template == 0:
        text = f"[A] {' '.join(pa)} [B] {' '.join(pb)} [관계] {' '.join(rel_s)} [종합] {' '.join(summ)}"
    elif template == 1:
        text = " ".join(pa + pb + rel_s + summ)
    elif template == 2:
        text = " ".join(rel_s + summ) + " " + " ".join(pa + pb)
    else:
        lines = pa + pb + rel_s + summ
        rnd.shuffle(lines)
        # "- " would trip the CSV formula-prefix guard in dataset.validate
        text = "\n".join("• " + x for x in lines)
    return text, template


def make_label_view(pair_id: str, A: dict, B: dict, F: dict) -> str:
    def person(tag, P):
        s, a = P["saju"], P["analysis"]
        pil = " · ".join(p if p else "(시주 없음)" for p in s["pillars"])
        return (f"[{tag}] {GENDER_KO.get(P['gender'], '성별 미입력')}, MBTI {P['mbti']}, 사주 {pil}\n"
                f"  일간 {_stem(a['day_stem'], 0)}, {a['season']}생, {a['strength']}(점수 {a['strength_score']}), "
                f"{a['climate']}(온도 {a['temp']:+g})\n"
                f"  필요한 기운 {'·'.join(ELEMENT_KO[e] for e in a['needs'])}, "
                f"기신 {ELEMENT_KO[a['gi']] if a['gi'] is not None else '-'}, "
                f"없는 오행 {'·'.join(ELEMENT_KO[e] for e in a['lacking']) or '-'}"
                + ("\n  생시 모름: 시주 제외" if not s["time_known"] else ""))

    rel_lines = []
    for r in F["relations"]:
        hua = f" →{ELEMENT_KO[r['hua']]}" if "hua" in r else ""
        tags = f" [{'; '.join(r['tags'])}]" if r.get("tags") else ""
        where = r.get("chars") and f"{r['chars']} (A:{r['a']} / B:{r['b']})" or f"A {r['a']} × B {r['b']}"
        rel_lines.append(f"  - {r['type']}: {where}{hua} (중요도 {r['rank']}){tags}")
    m = F["mbti"]
    return "\n".join([
        f"### {pair_id}",
        person("A", A), person("B", B),
        "[관계 목록]" if rel_lines else "[관계 목록] 없음",
        *rel_lines,
        "[종합 지표]",
        (f"  B→A 필요한 기운 공급 {F['supply_b_to_a']['level']}({F['supply_b_to_a']['share']}), "
        f"A→B {F['supply_a_to_b']['level']}({F['supply_a_to_b']['share']})"),
        (f"  오행 분포 유사도 {F['element_similarity']}, 온도 정반대 {'예' if F['opposite_climate'] else '아니오'}, "
        f"합친 온도 {F['combined_climate']}({F['combined_temp']:+g}), 같은 계절 {'예' if F['same_season'] else '아니오'}"),
        (f"  A가 본 B 일간 {F['a_sees_b']}{'(배우자성)' if F['spouse_a']['is_spouse_star'] else ''}, "
        f"B가 본 A 일간 {F['b_sees_a']}{'(배우자성)' if F['spouse_b']['is_spouse_star'] else ''}"),
        f"  MBTI 같은 글자 {''.join(m['same']) or '-'}({m['same_count']}개), 다른 글자 {', '.join(m['diff']) or '-'}",
    ])


def _hangul(s: str) -> str:
    """Hanja stems/branches/elements → Hangul readings (klue tokenizer has few hanja)."""
    from .constants import ELEMENTS

    table = {**STEM_KO, **BRANCH_KO, **dict(zip(ELEMENTS, (ELEMENT_KO[i] for i in range(5))))}
    return "".join(table.get(c, c) for c in s)


def make_fixed_text(A: dict, B: dict, F: dict) -> str:
    """Classifier input v3: the labeler's facts in one fixed order, Hangul only, with numbers.

    Same information as make_label_view (all relations, importance, tags, scores) minus the
    pair id; relations are sorted by importance so truncation drops the least important ones.
    """

    def els(es):
        return "·".join(ELEMENT_KO[e] for e in es) or "없음"

    def person(tag, P):
        s, a = P["saju"], P["analysis"]
        pil = " ".join(_hangul(p) if p else "시주없음" for p in s["pillars"])
        gi = ELEMENT_KO[a["gi"]] if a["gi"] is not None else "없음"
        return (
            f"[{tag}] {GENDER_KO.get(P['gender'], '성별미상')} MBTI {P['mbti']} 사주 {pil} | "
            f"일간 {_hangul(a['day_stem'])}{ELEMENT_KO[a['day_element']]} {a['season']}생 | "
            f"{a['strength']} {a['strength_score']} | {a['climate']} {a['temp']:+g} | "
            f"필요 {els(a['needs'])} | 기신 {gi} | 없는 오행 {els(a['lacking'])}"
            + (" | 생시 모름" if not s["time_known"] else "")
        )

    rels = []
    for r in sorted(F["relations"], key=lambda r: -r["rank"]):
        where = (
            f"{_hangul(r['chars'])} A{_hangul(r['a'])} B{_hangul(r['b'])}"
            if r.get("chars")
            else f"A {_hangul(r['a'])} B {_hangul(r['b'])}"
        )
        hua = f" →{ELEMENT_KO[r['hua']]}" if "hua" in r else ""
        tags = f" [{'; '.join(_hangul(t) for t in r['tags'])}]" if r.get("tags") else ""
        rels.append(f"{r['type']} 중요도{r['rank']} {where}{hua}{tags}")
    m, sa, sb = F["mbti"], F["supply_b_to_a"], F["supply_a_to_b"]
    summary = (
        f"[종합] B→A 공급 {sa['level']} {sa['share']} | A→B 공급 {sb['level']} {sb['share']} | "
        f"유사도 {F['element_similarity']} | 온도 정반대 {'예' if F['opposite_climate'] else '아니오'} | "
        f"합친 온도 {F['combined_climate']} {F['combined_temp']:+g} | "
        f"같은 계절 {'예' if F['same_season'] else '아니오'} | 같은 일간 오행 {'예' if F['same_day_element'] else '아니오'} | "
        f"A가 본 B {F['a_sees_b']}{' 배우자성' if F['spouse_a']['is_spouse_star'] else ''} | "
        f"B가 본 A {F['b_sees_a']}{' 배우자성' if F['spouse_b']['is_spouse_star'] else ''} | "
        f"MBTI 같은 글자 {''.join(m['same']) or '없음'} {m['same_count']}개"
    )
    return "\n".join(
        [
            person("A", A),
            person("B", B),
            summary,
            "[관계] " + (" / ".join(rels) if rels else "없음"),
        ]
    )


_TAG_SHORT = (("의 기신(", "기신누름("), ("에게 필요한 기운(", "필요막음("), ("합의 기운이 ", "합"))


def _short_tag(t: str) -> str:
    """'A의 기신(戌)을 눌러 줌' → 'A기신누름', 'A에게 필요한 기운(寅)을 막음' → 'A필요막음'."""
    if "눌러" in t:
        return t[0] + "기신누름"
    if "막음" in t:
        return t[0] + "필요막음"
    who = "A" if "A에게" in t else "B"
    return who + ("도움" if "도움" in t else "부담")


def make_compact_text(
    A: dict, B: dict, F: dict, v5: bool = False, shuffle_seed: int | None = None
) -> str:
    """Classifier input v4: make_fixed_text facts in short fixed tokens so it fits 512 tokens.

    v5=True adds two facts the model otherwise has to look up (error analysis on dev1200):
    the pillar position of each character in a 삼합/방합 (e.g. A월지해·시지자), and the
    per-letter MBTI comparison (EI둘다I SN다름 ...). Facts only, no rule points.
    shuffle_seed (training augmentation only): relations of equal importance appear in a
    random order, so the model cannot rely on their position.
    """
    def els(es):
        return "".join(ELEMENT_KO[e] for e in es) or "없음"

    def person(tag, P):
        a = P["analysis"]
        gi = ELEMENT_KO[a["gi"]] if a["gi"] is not None else "없음"
        # Pillars locate 일지/월지 inside 삼합·방합; element counts decide "없는 오행을 상대가 가짐".
        pil = " ".join(_hangul(p) if p else "없음" for p in P["saju"]["pillars"])
        cnt = "".join(f"{ELEMENT_KO[e]}{a['surface'][e]}" for e in range(5))
        return (f"{tag} {GENDER_KO.get(P['gender'], '미상')} {P['mbti']} 사주 {pil} 오행 {cnt} "
                f"일간 {_hangul(a['day_stem'])}{ELEMENT_KO[a['day_element']]} {a['season']} "
                f"{a['strength']} {a['strength_score']:.2f} "
                f"{a['climate']} 필요{els(a['needs'])} 기신{gi} 없는{els(a['lacking'])}"
                + (" 생시모름" if not P["saju"]["time_known"] else ""))

    def side(s):
        return _hangul(s.replace(" ", ""))

    def located(P, chars):
        """'亥子' → '월지해·시지자': where each branch sits in that person's pillars."""
        names = ("년지", "월지", "일지", "시지")
        out = []
        for c in chars:
            spots = [n for n, pil in zip(names, P["saju"]["pillars"], strict=True) if pil and pil[1] == c]
            out.extend(f"{n}{_hangul(c)}" for n in spots)
        return "·".join(out)

    ordered = list(F["relations"])
    if shuffle_seed is not None:
        random.Random(shuffle_seed).shuffle(ordered)  # stable sort below keeps this order on ties
    rels = []
    for r in sorted(ordered, key=lambda r: -r["rank"]):
        if v5 and r.get("chars"):
            where = f"A{located(A, r['a'])} B{located(B, r['b'])}"
        else:
            where = f"A{side(r['a'])} B{side(r['b'])}"
        tags = " ".join(_short_tag(t) for t in r.get("tags", []))
        rels.append(f"{r['type']}{r['rank']} {where}" + (f" {tags}" if tags else ""))
    m, sa, sb = F["mbti"], F["supply_b_to_a"], F["supply_a_to_b"]
    yn = lambda v: "예" if v else "아니오"
    summary = (f"공급 B→A {sa['level']} A→B {sb['level']} 유사도 {F['element_similarity']:.2f} "
               f"정반대 {yn(F['opposite_climate'])} 합친온도 {F['combined_climate']} "
               f"같은계절 {yn(F['same_season'])} 같은일간 {yn(F['same_day_element'])} "
               f"A→B {F['a_sees_b']}{'배우자성' if F['spouse_a']['is_spouse_star'] else ''} "
               f"B→A {F['b_sees_a']}{'배우자성' if F['spouse_b']['is_spouse_star'] else ''} "
               f"MBTI같음 {m['same_count']}")
    if v5:
        ma, mb = A["mbti"], B["mbti"]
        summary += " MBTI비교 " + " ".join(
            f"{k}{'둘다' + ma[i] if ma[i] == mb[i] else '다름'}"
            for i, k in enumerate(("EI", "SN", "TF", "JP"))
        )
    return "\n".join([person("A", A), person("B", B), summary,
                      "관계 " + (" / ".join(rels) if rels else "없음")])
