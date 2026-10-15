"""매운맛 궁합 신호. 커플 단위로만 계산하고 누가 해당하는지는 밖으로 내보내지 않는다."""
from __future__ import annotations

from .constants import (
    BRANCH_CLASH,
    BRANCH_SIX_COMBINE,
    BRANCH_WONJIN,
    DOHA,
    HONGYEOM,
    MAIN_HIDDEN,
    STEM_COMBINE,
)


def _branches(saju: dict) -> list[str]:
    return [p[1] for p in saju["pillars"] if p is not None]


def has_doha(saju: dict) -> bool:
    branches = _branches(saju)
    return any(DOHA[saju[pos][1]] in branches for pos in ("year", "day"))


def has_hongyeom(saju: dict) -> bool:
    return HONGYEOM[saju["day"][0]] in _branches(saju)


def spicy_signals(A: dict, B: dict) -> dict[str, bool]:
    """A, B: build_person() 결과. 대칭이라 A/B 순서와 무관하다."""
    sa, sb = A["saju"], B["saju"]
    da, db = sa["day"][1], sb["day"][1]
    key = frozenset((da, db))
    hidden = frozenset((MAIN_HIDDEN[da], MAIN_HIDDEN[db]))
    return {
        "doha": has_doha(sa) or has_doha(sb),
        "hongyeom": has_hongyeom(sa) or has_hongyeom(sb),
        "day_bond": da != db and (key in BRANCH_SIX_COMBINE or hidden in STEM_COMBINE),
        "day_clash": key in BRANCH_CLASH or key in BRANCH_WONJIN,
    }
