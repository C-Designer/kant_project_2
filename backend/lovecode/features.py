"""Classifier input from the API contract: Person → saju modules → pair text + limitations.

Training data (scripts/build_lovecode_dataset.py) and serving both go through pair_text(),
so the classifier always sees text produced by the same code path.
"""

import hashlib
import json

from .contracts import Person
from .saju import ManseInputError, build_pair, build_person

GENDER = {"male": "M", "female": "F", "unspecified": "U"}
VERSION = "lovecode-saju-v1/kst-dst-sect1"


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


def pair_text(a: Person, b: Person) -> tuple[str, list[str]]:
    """Deterministic and A/B swap invariant: canonical order, seed derived from the inputs."""
    sa, sb = to_saju_person(a), to_saju_person(b)
    keyed = sorted(
        ((json.dumps(p.model_dump(mode="json"), sort_keys=True), s) for p, s in ((a, sa), (b, sb))),
        key=lambda kv: kv[0],
    )
    seed = int(hashlib.sha256("|".join(k for k, _ in keyed).encode()).hexdigest()[:8], 16)
    text = build_pair(keyed[0][1], keyed[1][1], seed=seed)["text"]
    # Limitations keep the caller's person_a / person_b naming.
    return text, limitations(sa, sb)


__all__ = ["VERSION", "ManseInputError", "limitations", "pair_text", "to_saju_person"]
