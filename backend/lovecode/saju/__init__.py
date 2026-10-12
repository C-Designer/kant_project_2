"""사주 계산 → 분류 모델 입력 텍스트 (러브코드 2일차 모듈 이식, 검증: docs/labeling/calc_convention.md).

성별 U(미입력)는 배우자성 판단만 건너뛴다.
"""
from __future__ import annotations

import re

from .analysis import analyze_person
from .manse import ManseInputError, calc_saju
from .relations import analyze_pair
from .textgen import make_label_view, make_text

MBTI_RE = re.compile(r"^[EI][SN][TF][JP]$")


def build_person(gender: str, y: int, m: int, d: int, hour: int | None = None, minute: int | None = None,
                 mbti: str = "", sect: int = 1) -> dict:
    if gender not in ("M", "F", "U"):
        raise ManseInputError("성별은 M, F, U(미입력) 중 하나로 입력해 주세요.")
    mbti = mbti.upper().strip()
    if not MBTI_RE.match(mbti):
        raise ManseInputError(f"잘못된 MBTI 형식입니다: {mbti!r}")
    saju = calc_saju(y, m, d, hour, minute, sect=sect)
    return {"gender": gender, "mbti": mbti, "saju": saju.to_dict(), "analysis": analyze_person(saju)}


def build_pair(A: dict, B: dict, seed: int = 0, pair_id: str = "pair") -> dict:
    F = analyze_pair(A, B)
    text, template = make_text(A, B, F, seed)
    return {"features": F, "text": text, "template": template, "label_view": make_label_view(pair_id, A, B, F)}


__all__ = ["ManseInputError", "analyze_pair", "analyze_person", "build_pair", "build_person", "calc_saju"]
