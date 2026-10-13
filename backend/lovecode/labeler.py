"""Rule labeler: labeling guideline v1.2 (docs/labeling/labeling_guideline.md) as code.

Gaps in the guideline follow the conventions in docs/labeling/review_v12_notes.md section 1,
which the 600 AI-reviewed pairs already used. Same input → same label, so labels carry no
annotator noise. Each axis: sum saju signal points per pole (7-1); a gap of 1.5 or more
decides by saju, otherwise the section-2 MBTI column; if MBTI ties too, the higher saju pole;
if saju is exactly tied as well, the axis's section-6 final rule.
"""

from .saju.analysis import ten_god

AXES = {
    "케미": ("닮은꼴", "보완형"),
    "온도": ("열정형", "안정형"),
    "거리": ("밀착형", "독립형"),
    "갈등": ("바로 풀기", "시간 두기"),
}
HAP = {"육합", "반합", "암합", "삼합", "방합"}
CLASH = {"충", "천간충"}
HIDDEN_PARTS = {"원진", "해", "형"}
SUPPORT_GODS = {"비견", "겁재", "편인", "정인"}
FAMILY = {
    "비견": "비겁",
    "겁재": "비겁",
    "식신": "식상",
    "상관": "식상",
    "편재": "재성",
    "정재": "재성",
    "편관": "관성",
    "정관": "관성",
    "편인": "인성",
    "정인": "인성",
}


def _pos(side):
    """'일지 卯' → ('일', '지', '卯'); 삼합/방합 sides are bare character strings."""
    if " " not in side:
        return None, None, side
    p, c = side.split(" ", 1)
    return p[0], p[1], c


def _tags(r):
    t = r.get("tags", [])
    return {
        "press": any("기신" in x and "눌러" in x for x in t),
        "block": any("막음" in x for x in t),
        "help": any("도움" in x for x in t),
        "burden": any("부담" in x for x in t),
        "tagged": bool(t),
    }


def _kind(r):
    if r["type"] in HAP or r["type"] == "천간합":
        return "hap"
    if r["type"] in CLASH:
        return "clash"
    if set(r["type"].split("·")) & HIDDEN_PARTS:
        return "hidden"
    return None


def _relations(A, B, F):
    """Normalise relations; the same character pair counts once per kind (convention 4)."""
    da, db = A["saju"]["day"][1], B["saju"]["day"][1]
    ma, mb = A["saju"]["month"][1], B["saju"]["month"][1]
    best = {}
    for r in F["relations"]:
        kind = _kind(r)
        if kind is None:
            continue
        pa, ka, ca = _pos(r["a"])
        pb, _kb, cb = _pos(r["b"])
        if r["type"] in ("삼합", "방합"):
            both_day = da in ca and db in cb
            spot = (
                "day"
                if both_day
                else ("month" if (ma in ca or mb in cb or da in ca or db in cb) else "other")
            )
            key = (kind, frozenset(ca + cb))
        else:
            if {pa, pb} == {"일"}:
                spot = "day"
            elif pa in "일월" and pb in "일월":
                spot = "month"  # 월지끼리 or 일지×월지 교차: same weight (6절)
            else:
                spot = "other"
            key = (kind, frozenset((ca, cb)))
        stem = ka == "간"
        rec = {
            "type": r["type"],
            "kind": kind,
            "rank": r["rank"],
            "spot": spot,
            "stem": stem,
            "day_stems": stem and pa == pb == "일",
            "tags": _tags(r),
        }
        old = best.get(key)
        if old is None or rec["rank"] > old["rank"]:
            best[key] = rec
        elif rec["rank"] == old["rank"]:  # equal importance: merge tags
            old["tags"] = {k: old["tags"][k] or rec["tags"][k] for k in old["tags"]}
    # 6절: a pair with both 충 and 형/원진/해 counts once, as 충.
    clash_pairs = {k[1] for k, v in best.items() if v["kind"] == "clash"}
    best = {k: v for k, v in best.items() if not (v["kind"] == "hidden" and k[1] in clash_pairs)}
    # A 삼합/방합 that contains an already counted 합 pair counts with it once.
    pairs = {k[1] for k, v in best.items() if v["kind"] == "hap" and len(k[1]) == 2}
    return [
        x
        for k, x in best.items()
        if not (x["type"] in ("삼합", "방합") and any(p <= k[1] for p in pairs))
    ]


def _clash_temp_weight(t):
    if not t["tagged"]:
        return 0.5
    if t["press"] and t["block"]:
        return 0.75
    return 1.0 if t["press"] else 0.5


def _decide(axis, s0, s1, m0, m1, final):
    """7-1. Returns (pole index, how)."""
    if abs(s0 - s1) >= 1.5:
        return (0 if s0 > s1 else 1), "saju"
    if m0 != m1:
        return (0 if m0 > m1 else 1), "mbti"
    if s0 != s1:
        return (0 if s0 > s1 else 1), "saju_slight"
    return final(), "final"


def label(A, B, F):
    a, b = A["analysis"], B["analysis"]
    ma, mb = A["mbti"], B["mbti"]
    rels = _relations(A, B, F)
    same = sum(x == y for x, y in zip(ma, mb))
    both = lambda ch: ch in ma and ch in mb
    sp_a, sp_b = F["spouse_a"]["is_spouse_star"], F["spouse_b"]["is_spouse_star"]
    spouse = sp_a or sp_b
    day_hap = any(x["day_stems"] and x["type"] == "천간합" for x in rels)
    out, scores = {}, {}

    # 케미: 닮은꼴(0) / 보완형(1)
    s0 = s1 = 0.0
    sim = F["element_similarity"]
    s0 += sim >= 0.85
    s0 += F["same_day_element"]
    s0 += F["same_season"]
    na, nb = set(a["needs"]), set(b["needs"])
    s0 += 1.0 if na and na == nb else (0.5 if na & nb else 0)
    s1 += sim < 0.65
    s1 += 2 * F["opposite_climate"]
    la, lb = F["supply_b_to_a"]["level"], F["supply_a_to_b"]["level"]
    s1 += 2 if la == lb == "많음" else (0.5 if "많음" in (la, lb) else 0)
    sa, sb = A["analysis"]["surface"], B["analysis"]["surface"]
    s1 += 1 if any(sb[e] for e in a["lacking"]) or any(sa[e] for e in b["lacking"]) else 0
    m0, m1 = same >= 3, same <= 1
    out["케미"] = _decide("케미", s0, s1, m0, m1, lambda: 0 if sim >= 0.75 else 1)
    scores["케미"] = (s0, s1)

    # 온도: 열정형(0) / 안정형(1)
    s0 = s1 = 0.0
    for x in rels:
        if x["day_stems"] and x["type"] in ("천간합", "천간충"):
            s0 += 0.5 if (x["type"] == "천간충" and not x["tags"]["tagged"]) else 2
        elif x["kind"] == "clash" and x["rank"] >= 2:
            s0 += _clash_temp_weight(x["tags"])
    s0 += spouse
    s0 += F["combined_climate"] == "뜨거움" or "뜨거움" in (a["climate"], b["climate"])
    strong_clash = any(x["kind"] == "clash" and x["rank"] >= 2 for x in rels)
    s1 += any(x["type"] in HAP for x in rels) and not strong_clash
    s1 += F["a_sees_b"] in SUPPORT_GODS or F["b_sees_a"] in SUPPORT_GODS
    s1 += F["combined_climate"] == "차가움"
    s1 += a["climate"] == b["climate"] == "온화"
    m0, m1 = both("F") + both("E"), both("T") + both("I")
    fam = FAMILY[ten_god(A["saju"]["day"][0], B["saju"]["day"][0])]
    out["온도"] = _decide(
        "온도", s0, s1, m0, m1, lambda: 0 if (day_hap or spouse or fam in ("재성", "관성")) else 1
    )
    scores["온도"] = (s0, s1)

    # 거리: 밀착형(0) / 독립형(1)
    s0 = s1 = 0.0
    day = [x for x in rels if x["spot"] == "day" and not x["stem"]]
    day_hap_b = any(x["kind"] == "hap" for x in day)
    day_bad = any(x["kind"] in ("clash", "hidden") for x in day)
    s0 += 2 * day_hap_b
    s1 += 2 * day_bad
    if day_hap_b and day_bad:
        s0 += 0.5
    if not day:
        s1 += 1
    for x in rels:
        if x["spot"] == "month" and not x["stem"]:
            if x["kind"] == "hap":
                s0 += 1
            elif x["kind"] == "clash":
                s1 += 1
            else:
                s1 += 0.5
    s0 += spouse or day_hap
    s0 += (a["strength"] == "신약" and la == "많음") or (b["strength"] == "신약" and lb == "많음")
    s1 += a["strength"] == b["strength"] == "신강"
    ei = both("E") - both("I")
    jp = both("J") - both("P")
    m0, m1 = (ei > 0, ei < 0) if ei else (jp > 0, jp < 0)
    out["거리"] = _decide("거리", s0, s1, m0, m1, lambda: 1)
    scores["거리"] = (s0, s1)

    # 갈등: 바로 풀기(0) / 시간 두기(1). Section 2-4 signals are presence-based (one point
    # each, not per relation): which conflict is heavier, 충 pressing a 기신, 원진·해·형
    # blocking a need, strength. 일지끼리 relations are the 2-point strong signal instead of
    # the "heavier" point. Untagged relations add 0.5 and stay out of the comparison.
    s0 = s1 = 0.0
    clashes = [x for x in rels if x["kind"] == "clash"]
    # A hidden conflict tagged only "기신 눌러 줌" is not a hidden conflict (6절).
    hidden = [
        x for x in rels if x["kind"] == "hidden" and (x["tags"]["block"] or not x["tags"]["tagged"])
    ]
    has_clash = bool(clashes)
    tc = [x for x in clashes if x["tags"]["tagged"]]
    th = [x for x in hidden if x["tags"]["tagged"]]
    s0 += 0.5 * any(not x["tags"]["tagged"] for x in clashes)
    s1 += 0.5 * any(not x["tags"]["tagged"] for x in hidden)
    strong_c = any(x["spot"] == "day" and not x["stem"] for x in tc) or any(
        x["day_stems"] for x in tc
    )
    strong_h = any(x["spot"] == "day" and not x["stem"] for x in th)
    s0 += 2 * strong_c
    s1 += 2 * strong_h
    if not (strong_c or strong_h):
        if not has_clash:
            s1 += 1  # 충이 없다
        elif tc:
            rc = max(x["rank"] for x in tc)
            rh = max((x["rank"] for x in th), default=0)
            if rc > rh:
                s0 += 1
            elif rh > rc:
                s1 += 1
            else:  # 6절: same importance → tags before counts
                c_press = any(x["tags"]["press"] for x in tc)
                h_block = any(x["tags"]["block"] for x in th)
                if c_press and h_block:
                    s0 += 1
                elif not c_press and h_block:
                    s1 += 1
    s0 += any(x["tags"]["press"] for x in tc)
    s1 += any(x["tags"]["block"] for x in th)
    s0 += "신강" in (a["strength"], b["strength"])
    s1 += a["strength"] == b["strength"] == "신약"
    m0, m1 = both("T") + both("E"), both("F") + both("I")
    out["갈등"] = _decide(
        "갈등",
        s0,
        s1,
        m0,
        m1,
        lambda: 0 if both("T") else (1 if both("F") else (0 if has_clash else 1)),
    )
    scores["갈등"] = (s0, s1)

    poles = {ax: AXES[ax][out[ax][0]] for ax in AXES}
    idx = 0
    for ax in AXES:
        idx = idx * 2 + out[ax][0]
    soft = sum(out[ax][1] != "saju" for ax in AXES)
    full_tie = any(out[ax][1] == "final" for ax in AXES)
    confidence = "high" if soft == 0 else ("low" if soft >= 3 or full_tie else "mid")
    return {
        **poles,
        "type_id": f"T{idx + 1:02d}",
        "confidence": confidence,
        "decided_by": {ax: out[ax][1] for ax in AXES},
        "scores": scores,
    }
