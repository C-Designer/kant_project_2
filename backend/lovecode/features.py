"""Model inputs from the API contract: Person → saju modules → texts + limitations.

compact_text() is the rule5 classifier input (same builder as scripts/build_rule_dataset.py),
pair_text() the narrative explanation input; analysis_inputs() derives both from one chart.
"""

import hashlib
import json

from .contracts import Person
from .labeler import label
from .reading import Basis
from .saju import ManseInputError, analyze_pair, build_pair, build_person
from .saju.constants import ELEMENT_KO, STEM_ELEMENT, STEM_KO
from .saju.spicy import spicy_signals

GENDER = {"male": "M", "female": "F", "unspecified": "U"}
VERSION = "lovecode-saju-v1/kst-dst-sect1"


def day_stem_ko(person: dict) -> str:
    """'丁' → '정화' (stem + its element), the way the narrative spells it in Hangul."""
    c = person["saju"]["day"][0]
    return STEM_KO[c] + ELEMENT_KO[STEM_ELEMENT[c]]


def to_saju_person(p: Person) -> dict:
    hour = minute = None
    if p.birth_time is not None:
        hour, minute = map(int, p.birth_time.split(":"))
    d = p.birth_date
    return build_person(GENDER[p.gender], d.year, d.month, d.day, hour, minute, p.mbti)


def limitations(a: dict, b: dict) -> list[str]:
    out = []
    for suffix, person in (("a", a), ("b", b)):
        saju = person["saju"]
        if not saju["time_known"]:
            out.append("missing_hour_" + suffix)
        if any("달라질 수 있음" in n for n in saju["notes"]):
            out.append("boundary_time_unknown_" + suffix)
    return out


def _canonical(a: Person, b: Person, sa: dict, sb: dict) -> tuple[dict, dict, int]:
    """Canonical A/B order and a seed derived from the inputs, so texts are swap invariant."""
    keyed = sorted(
        ((json.dumps(p.model_dump(mode="json"), sort_keys=True), s) for p, s in ((a, sa), (b, sb))),
        key=lambda kv: kv[0],
    )
    seed = int(hashlib.sha256("|".join(k for k, _ in keyed).encode()).hexdigest()[:8], 16)
    return keyed[0][1], keyed[1][1], seed


def _narrative(first: dict, second: dict, seed: int) -> str:
    return build_pair(first, second, seed=seed)["text"]


def _compact(first: dict, second: dict, pair: dict | None = None) -> str:
    from .saju.textgen import make_compact_text

    return make_compact_text(first, second, pair or analyze_pair(first, second), v5=True)


def pair_text(a: Person, b: Person) -> tuple[str, list[str]]:
    """Narrative explanation text (same builder as the explanation evaluation sets)."""
    sa, sb = to_saju_person(a), to_saju_person(b)
    # Limitations keep the caller's person_a / person_b naming.
    return _narrative(*_canonical(a, b, sa, sb)), limitations(sa, sb)


def compact_text(a: Person, b: Person) -> tuple[str, list[str]]:
    """Input for the rule-label classifiers (data/lovecode-rule5, v5 compact text).

    Same text builder as scripts/build_rule_dataset.py --text v5. Canonical A/B order keeps
    it swap invariant; the final model was also trained with A/B-swapped copies.
    """
    sa, sb = to_saju_person(a), to_saju_person(b)
    first, second, _ = _canonical(a, b, sa, sb)
    return _compact(first, second), limitations(sa, sb)


def analysis_inputs(a: Person, b: Person) -> dict:
    """One saju computation for a web request: classifier text, explanation text, limitations.

    Both texts come from the same charts, so the classifier and the explainer never read
    different pillars for the same person.
    """
    sa, sb = to_saju_person(a), to_saju_person(b)
    first, second, seed = _canonical(a, b, sa, sb)
    pair = analyze_pair(first, second)
    return {
        "compact": _compact(first, second, pair),
        "narrative": _narrative(first, second, seed),
        "limitations": limitations(sa, sb),
        # Couple-level flags only; which person has a 신살 is never passed on.
        "spicy_signals": spicy_signals(first, second),
        # Rule signals behind each axis, for the '왜 이 유형일까' reading. The narrative
        # names `first` A, which is the caller's person_b when the order was swapped.
        "basis": Basis(
            rule=label(first, second, pair),
            swapped=first is not sa,
            day_stems=(day_stem_ko(first), day_stem_ko(second)),
        ),
    }


__all__ = [
    "VERSION",
    "ManseInputError",
    "analysis_inputs",
    "compact_text",
    "limitations",
    "pair_text",
    "to_saju_person",
]
