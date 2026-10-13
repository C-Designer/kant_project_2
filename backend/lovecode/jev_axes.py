"""Jev v2: English JSON facts + one Choice question per axis (post-hoc experiment).

Changes from jev_classifier (v1, Korean compact text + one 16-way question):
1. State facts are an English JSON object built from the same persons/relations the Korean text
   is rendered from (same information, no rule points precomputed). Docs: English is the
   primary training language; object states with named fields are recommended.
2. Four Choice questions (one per axis), each with only that axis's rules; the 16-type answer is
   the combination, and its probability is the product of the axis probabilities.
The labeling procedure is given, so results are "rule-following", not independent judgment.
"""

import time

from .contracts import TAXONOMY
from .jev_classifier import MODEL, JevClassifier
from .saju.analysis import ten_god
from .saju.constants import STEM_ELEMENT

ELEMENTS = ["wood", "fire", "earth", "metal", "water"]
ROMAN = dict(zip("甲乙丙丁戊己庚辛壬癸", ["Gap", "Eul", "Byeong", "Jeong", "Mu", "Gi", "Gyeong", "Sin", "Im", "Gye"]))
ROMAN |= {k: v + "-br" for k, v in zip("子丑寅卯辰巳午未申酉戌亥",
                                     ["Ja", "Chuk", "In", "Myo", "Jin", "Sa", "O", "Mi", "Sin", "Yu", "Sul", "Hae"])}
POS = {"년": "year", "월": "month", "일": "day", "시": "hour"}
KIND = {"간": "stem", "지": "branch"}
REL = {
    "천간합": "stem_combination", "천간충": "stem_clash", "육합": "six_combination",
    "반합": "half_combination", "삼합": "triple_combination", "방합": "directional_combination",
    "암합": "hidden_combination", "충": "clash", "원진": "resentment", "해": "harm", "형": "punishment",
}
SEASON = {"봄": "spring", "여름": "summer", "가을": "autumn", "겨울": "winter"}
STRENGTH = {"신강": "strong", "신약": "weak", "중화": "balanced"}
CLIMATE = {"차가움": "cold", "뜨거움": "hot", "온화": "mild", "균형": "balanced"}
LEVEL = {"많음": "many", "보통": "some", "적음": "few"}
GOD = {
    "비견": "peer", "겁재": "rival", "식신": "eating_god", "상관": "hurting_officer",
    "편재": "indirect_wealth", "정재": "direct_wealth", "편관": "seven_killings",
    "정관": "direct_officer", "편인": "indirect_resource", "정인": "direct_resource",
}
GOD_FAMILY = {
    "peer": "self", "rival": "self", "eating_god": "output", "hurting_officer": "output",
    "indirect_wealth": "wealth", "direct_wealth": "wealth", "seven_killings": "officer",
    "direct_officer": "officer", "indirect_resource": "resource", "direct_resource": "resource",
}
AXIS_KEYS = ["chemistry", "temperature", "distance", "conflict"]
POLES = {
    "chemistry": (("Similar", "닮은꼴", "alike temperaments feel comfortable"),
                  ("Complementary", "보완형", "each fills what the other lacks")),
    "temperature": (("Passionate", "열정형", "strong, changing emotional expression"),
                    ("Steady", "안정형", "calm, consistent")),
    "distance": (("Close", "밀착형", "time together comes first"),
                 ("Independent", "독립형", "each keeps their own space")),
    "conflict": (("ResolveNow", "바로 풀기", "talk it out on the spot"),
                 ("TakeTime", "시간 두기", "cool down, then talk")),
}

PROCEDURE = (
    "Decide the asked axis only, in these steps. Step 1: list every saju point of that axis's "
    "rules for each pole (count a relation between the same two characters once, at its highest "
    "importance; if the same two characters have both a clash and resentment/harm/punishment, "
    "count only the clash; 'tagged' means the relation has at least one tag). Step 2: compute the "
    "gap = |points of pole 1 - points of pole 2|. Step 3: if the gap is 1.5 or more, answer the "
    "pole with more saju points and stop. Step 4: if the gap is below 1.5, IGNORE which pole the "
    "saju points lean to and apply that axis's MBTI rule using couple.pair.mbti_comparison; if it "
    "picks a pole, answer it and stop. Step 5: only if the MBTI rule is a tie, answer the pole "
    "with more saju points; if the points are exactly equal, apply that axis's tie rule."
)
AXIS_RULES = {
    "chemistry": (
        "Similar points: element_similarity >= 0.85 (+1); same_day_element (+1); same_season (+1); "
        "needed_elements of A and B identical (+1) or only overlapping (+0.5). Complementary points: "
        "element_similarity < 0.65 (+1); opposite_temperatures (+2); supply both directions 'many' "
        "(+2) or exactly one direction 'many' (+0.5); an element missing for one person has a "
        "count > 0 in the other person's element_counts (+1, at most once). MBTI rule: "
        "same_mbti_letters 3-4 -> Similar, 0-1 -> Complementary, 2 -> tie. Tie rule: "
        "element_similarity >= 0.75 -> Similar, else Complementary."
    ),
    "temperature": (
        "Passionate points: stem_combination between the two day stems (+2); stem_clash between the "
        "two day stems (+2 if tagged, +0.5 if untagged); every other clash or stem_clash with "
        "importance >= 2 (+1 if it presses a harmful element only, +0.5 if it blocks a need only, "
        "+0.75 if both, +0.5 if untagged); spouse_star for A or B (+1); combined_temperature hot or "
        "either person's chart_temperature hot (+1). Steady points: at least one six/half/triple/"
        "directional/hidden combination and no clash or stem_clash with importance >= 2 (+1); "
        "ten_god A_sees_B or B_sees_A is peer, rival, indirect_resource or direct_resource (+1); "
        "combined_temperature cold (+1); both persons mild (+1). MBTI rule: Passionate votes = "
        "(both F) + (both E), Steady votes = (both T) + (both I); more votes wins, equal = tie. "
        "Tie rule: Passionate if day stems form a stem_combination, a spouse_star exists, or the "
        "day-stem ten_god family is wealth or officer; else Steady."
    ),
    "distance": (
        "Day-branch relations (A day branch with B day branch, or a triple/directional combination "
        "containing both day branches): any combination -> Close +2; any clash/resentment/harm/"
        "punishment -> Independent +2 regardless of tags; if both exist Close gets +0.5 more; no "
        "day-branch relation at all -> Independent +1. Month-involved branch relations (month-month "
        "or day-month branches): combination Close +1, clash Independent +1, resentment/harm/"
        "punishment Independent +0.5 each. A spouse_star or a day-stem stem_combination: Close +1. "
        "A weak person whose supply from the partner is 'many': Close +1. Both persons strong: "
        "Independent +1. MBTI rule: both E -> Close, both I -> Independent; if E/I differ: both J "
        "-> Close, both P -> Independent; else tie. Tie rule: Independent."
    ),
    "conflict": (
        "Clash means clash or stem_clash; hidden means resentment/harm/punishment, except a hidden "
        "relation whose only tags press a harmful element (ignore it). Untagged clash present: "
        "ResolveNow +0.5. Untagged hidden present: TakeTime +0.5. Strong signals: a tagged clash "
        "between day branches or between day stems -> ResolveNow +2; a tagged hidden between day "
        "branches that blocks a need -> TakeTime +2. If there is no strong signal: no clash at all "
        "-> TakeTime +1; otherwise compare the highest importance of tagged clashes with tagged "
        "hidden relations: higher side +1; if equal, ResolveNow +1 when some clash presses a harmful "
        "element and some hidden blocks a need, TakeTime +1 when no clash presses and some hidden "
        "blocks. Any tagged clash pressing a harmful element: ResolveNow +1. Any tagged hidden "
        "blocking a need: TakeTime +1. Either person strong: ResolveNow +1. Both weak: TakeTime +1. "
        "MBTI rule: ResolveNow votes = (both T) + (both E), TakeTime votes = (both F) + (both I). "
        "Tie rule: both T -> ResolveNow, both F -> TakeTime, else ResolveNow if any clash exists, "
        "otherwise TakeTime."
    ),
}


def _side(s):
    if " " not in s:  # triple/directional combination: bare characters
        return {"characters": [ROMAN.get(c, c) for c in s]}
    p, c = s.split(" ", 1)
    return {"position": f"{POS[p[0]]} {KIND[p[1]]}", "character": ROMAN.get(c, c)}


def _tag(t):
    who = t[0]
    if "눌러" in t:
        return f"presses {who}'s harmful element"
    if "막음" in t:
        return f"blocks what {who} needs"
    return f"combination {'helps' if '도움' in t else 'burdens'} {'A' if 'A에게' in t else 'B'}"


def _person(P):
    a, s = P["analysis"], P["saju"]
    return {
        "gender": {"M": "male", "F": "female"}.get(P["gender"], "unspecified"),
        "mbti": P["mbti"],
        "pillars": {
            k: (" ".join(ROMAN[c] for c in p) if p else "unknown")
            for k, p in zip(["year", "month", "day", "hour"], s["pillars"], strict=True)
        },
        "day_branch": ROMAN[s["day"][1]],
        "month_branch": ROMAN[s["month"][1]],
        "birth_hour_known": s["time_known"],
        "day_stem_element": ELEMENTS[a["day_element"]],
        "season": SEASON[a["season"].removesuffix("생")] if a["season"].removesuffix("생") in SEASON else a["season"],
        "strength": STRENGTH[a["strength"]],
        "strength_score": a["strength_score"],
        "chart_temperature": CLIMATE[a["climate"]],
        "element_counts": dict(zip(ELEMENTS, a["surface"], strict=True)),
        "needed_elements": [ELEMENTS[e] for e in a["needs"]],
        "harmful_element": ELEMENTS[a["gi"]] if a["gi"] is not None else None,
        "missing_elements": [ELEMENTS[e] for e in a["lacking"]],
    }


def _mbti_comparison(ma, mb):
    """Per-letter facts the MBTI rules read: 'both E', 'both I' or 'different'."""
    out = {}
    for i, key in enumerate(["E_I", "S_N", "T_F", "J_P"]):
        out[key] = f"both {ma[i]}" if ma[i] == mb[i] else "different"
    return out


def english_facts(A, B, F):
    rels = []
    for r in sorted(F["relations"], key=lambda r: -r["rank"]):
        rel = {
            "type": " + ".join(REL[t] for t in r["type"].split("·")),
            "importance": r["rank"],
            "A": _side(r["a"]),
            "B": _side(r["b"]),
            "tags": [_tag(t) for t in r.get("tags", [])],
        }
        if "hua" in r:
            rel["transforms_to"] = ELEMENTS[r["hua"]]
        rels.append(rel)
    god_ab = GOD[ten_god(A["saju"]["day"][0], B["saju"]["day"][0])]
    return {
        "A": _person(A),
        "B": _person(B),
        "pair": {
            "supply_B_to_A": LEVEL[F["supply_b_to_a"]["level"]],
            "supply_A_to_B": LEVEL[F["supply_a_to_b"]["level"]],
            "element_similarity": F["element_similarity"],
            "opposite_temperatures": F["opposite_climate"],
            "combined_temperature": CLIMATE[F["combined_climate"]],
            "same_season": F["same_season"],
            "same_day_element": F["same_day_element"],
            "ten_god_A_sees_B": god_ab,
            "ten_god_B_sees_A": GOD[ten_god(B["saju"]["day"][0], A["saju"]["day"][0])],
            "day_stem_ten_god_family": GOD_FAMILY[god_ab],
            "spouse_star_for_A": F["spouse_a"]["is_spouse_star"],
            "spouse_star_for_B": F["spouse_b"]["is_spouse_star"],
            "same_mbti_letters": F["mbti"]["same_count"],
            "mbti_comparison": _mbti_comparison(A["mbti"], B["mbti"]),
            "day_stems_same_element": STEM_ELEMENT[A["saju"]["day"][0]] == STEM_ELEMENT[B["saju"]["day"][0]],
        },
        "relations": rels,
    }


def request_body(A, B, F):
    state = {"couple": english_facts(A, B, F), "procedure": PROCEDURE,
             "rules": {k: AXIS_RULES[k] for k in AXIS_KEYS}}
    questions = {
        ax: {
            "type": "choice",
            "instructions": f"Following procedure and rules.{ax}, which {ax} pole fits this couple?",
            "criteria": {en: f"{ko}: {desc}" for en, ko, desc in POLES[ax]},
        }
        for ax in AXIS_KEYS
    }
    return {"state": state, "model": MODEL, "questions": questions}


class JevAxesClassifier(JevClassifier):
    """classify_pair(A, B, F) -> (type_id | None, meta) with per-axis and 16-type probabilities."""

    def __init__(self, transport=None, retries=3):
        super().__init__("guided", transport=transport, retries=retries)
        self.prompt_version = "jev-axes-json-v2"

    def classify_pair(self, A, B, F, *, allow_paid=False):
        meta = {"backend": "jev", "model": self.model, "prompt_version": self.prompt_version,
                "settings": {"mode": "axes-json"}, "error": None, "usage": {}}
        if not allow_paid:
            meta.update(error="API_DISABLED", elapsed_seconds=0.0)
            return None, meta
        start = time.perf_counter()
        try:
            data = self._post(request_body(A, B, F))
            answers = data["answers"]
            axis_p = {}
            for ax in AXIS_KEYS:
                probs = answers[ax]["probabilities"]
                axis_p[ax] = [probs.get(POLES[ax][0][0], 0.0), probs.get(POLES[ax][1][0], 0.0)]
        except Exception as e:  # noqa: BLE001 - network/HTTP/shape errors map to one code
            meta.update(error=f"PROVIDER_REQUEST_FAILED:{type(e).__name__}",
                        elapsed_seconds=time.perf_counter() - start)
            return None, meta
        meta["elapsed_seconds"] = time.perf_counter() - start
        meta["usage"] = data.get("usage", {})
        meta["model"] = data.get("model", self.model)
        meta["axis_probabilities"] = axis_p
        # 16-type probability = product of the axis probabilities (axes answered independently).
        probs = {}
        for i, k in enumerate(TAXONOMY):
            bits = [(i >> (3 - j)) & 1 for j in range(4)]
            p = 1.0
            for ax, bit in zip(AXIS_KEYS, bits, strict=True):
                p *= axis_p[ax][bit]
            probs[k] = p
        total = sum(probs.values()) or 1.0
        meta["probabilities"] = {k: v / total for k, v in probs.items()}
        pred = max(meta["probabilities"], key=meta["probabilities"].get)
        meta["confidence"] = meta["probabilities"][pred]
        return pred, meta
