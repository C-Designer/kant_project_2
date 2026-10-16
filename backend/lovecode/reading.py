"""'왜 이 유형일까' 풀이: 사람별 사주 풀이 + 축별 근거, explainer 호출에 덧붙인다.

The classifier (BERT) picks the type; the rule labeler (labeler.py) is re-run on the same
charts only to say *why*. For each axis the explainer gets the saju and MBTI signals that
point to the pole the classifier chose, never the other pole's, so it cannot argue for a
type the couple did not get. When the rules lean the other way the prompt says so plainly
("규칙 신호만으로는 팽팽함") and the explainer falls back to the couple's overall picture.

The narrative names the people A/B in canonical order, which is the caller's order
reversed when `swapped`. The prompt maps A/B to the screen's names ('첫 번째 분' = the form's
01) and the output fields follow the caller's order; each reading is checked against that
person's day stem so a mix-up is repaired (or the reading dropped) rather than shown.
"""

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from .checks import HARD, text_problems
from .contracts import (
    AXIS_KEYS,
    AXIS_LABELS,
    AXIS_VALUES,
    READING_AXIS_MAX,
    READING_PERSON_MAX,
    TAXONOMY,
    Reading,
)

READING_VERSION = "reading-v1"
NAMES = ("첫 번째 분", "두 번째 분")  # person_a, person_b, as numbered 01/02 on the form
PERSON_MAX = READING_PERSON_MAX
AXIS_MAX = READING_AXIS_MAX
PERSON_LETTER = re.compile(r"(?<![A-Za-z])[AB](?![A-Za-z])")
RULE_AXES = ("케미", "온도", "거리", "갈등")  # labeler names, same order as AXIS_KEYS
HOW = {
    "saju": "사주 신호 차이가 뚜렷해 사주로 정해졌다",
    "mbti": "사주 신호가 비슷해서 MBTI 성향이 방향을 정했다",
    "saju_slight": "사주 신호가 근소하게 앞서 정해졌다",
    "final": "신호가 팽팽해 두 사람 전체 기질을 보고 정해졌다",
}


@dataclass
class Basis:
    """Labeler output for the canonical A/B pair, whether A is the caller's person_b, and
    A's and B's day stems in Hangul (e.g. '정화')."""

    rule: dict
    swapped: bool
    day_stems: tuple[str, str]

    def caller_stems(self):
        return tuple(reversed(self.day_stems)) if self.swapped else self.day_stems


PEOPLE_FIELDS = ("first_person", "second_person")


class ReadingDraft(BaseModel):
    first_person: str = Field(description="'첫 번째 분'의 사주·MBTI 풀이")
    second_person: str = Field(description="'두 번째 분'의 사주·MBTI 풀이")
    chemistry: str = Field(description="연애 케미 축이 이 극으로 나온 이유")
    temperature: str = Field(description="연애 온도 축이 이 극으로 나온 이유")
    distance: str = Field(description="관계 거리 축이 이 극으로 나온 이유")
    conflict: str = Field(description="갈등 해결 축이 이 극으로 나온 이유")


def names(basis):
    """Korean names for the narrative's A and B."""
    return (NAMES[1], NAMES[0]) if basis.swapped else NAMES


def axis_evidence(basis, type_id):
    """One block per axis: the chosen pole, its supporting signals and how it was decided."""
    axes = TAXONOMY[type_id]["axes"]
    blocks = []
    for key, rule_ax, labels, values in zip(
        AXIS_KEYS, RULE_AXES, AXIS_LABELS, AXIS_VALUES, strict=True
    ):
        pole = values.index(axes[key])
        signals = basis.rule["signals"][rule_ax]
        saju = signals["saju"][pole]
        # MBTI only counts as support when it leans this way (a tie is no support).
        mbti = signals["mbti"][pole] if len(signals["mbti"][pole]) > len(signals["mbti"][1 - pole]) else []
        agreed = basis.rule[rule_ax] == labels[pole]
        how = HOW[basis.rule["decided_by"][rule_ax]] if agreed else (
            "규칙 신호만으로는 팽팽해서, 분류 모델이 두 사람 데이터 전체 흐름을 보고 정했다"
        )
        blocks.append(
            f"- {labels[pole]} ({key})\n"
            f"  사주 근거: {'; '.join(saju) if saju else '이 방향의 뚜렷한 사주 신호는 적음'}\n"
            f"  MBTI 근거: {', '.join(mbti) if mbti else '이 방향으로 기운 MBTI 신호 없음'}\n"
            f"  판단 과정: {how}"
        )
    return "\n".join(blocks)


def reading_prompt(basis, type_id):
    a_name, b_name = names(basis)
    a_stem, b_stem = basis.day_stems
    first, second = basis.caller_stems()
    first_tag, second_tag = ("B", "A") if basis.swapped else ("A", "B")
    return (
        "[왜 이 유형일까 reading]\n"
        f"입력 데이터의 A는 '{a_name}'(일간 {a_stem}), B는 '{b_name}'(일간 {b_stem})이다. "
        "해설 어디에서도 A, B 같은 영문자 대신 이 호칭을 쓴다.\n"
        f"- first_person: '첫 번째 분'(입력의 {first_tag}, 일간 {first})이 어떤 사람인지 사주와 MBTI로 "
        f"풀어 쓴다. 2~3문장, {PERSON_MAX}자 이하. 일간({first})과 그 오행의 성질, 태어난 계절, "
        "기운의 강약(신강·신약), 필요한 기운을 입력에 있는 만큼 쓰고, 그래서 연애할 때 어떤 모습일지까지 "
        "잇는다. MBTI는 '외향적이고 감정을 중시하는 성향'처럼 풀어 쓴다. 호칭은 쓰지 않아도 된다"
        "(화면에 따로 보인다).\n"
        f"- second_person: '두 번째 분'(입력의 {second_tag}, 일간 {second})을 같은 방식으로 쓴다.\n"
        f"- chemistry, temperature, distance, conflict: 각 축이 왜 그 극으로 나왔는지 2~3문장, "
        f"{AXIS_MAX}자 이하. 아래 '축별 근거'에 있는 신호를 구체적으로 짚고(예: '두 분의 일지가 "
        "정면으로 부딪치는 충이라'), 그 신호가 두 사람 관계에서 어떻게 나타나는지 이어 쓴다. "
        "근거가 적다고 적힌 축은 두 사람 풀이를 바탕으로 자연스럽게 설명하고, 근거를 지어내지 않는다.\n"
        "- 사주 용어(일간, 일지, 충, 육합, 원진, 신강 등)는 한글로 쓰고 처음 나올 때 쉬운 말로 풀어 준다. "
        "한자, 생일, 시각, 성별은 쓰지 않는다. 존댓말로 쓴다.\n"
        "- 이 섹션도 각 축은 이 커플의 극 이름만 쓴다.\n"
        "축별 근거(규칙이 계산한 사실):\n" + axis_evidence(basis, type_id)
    )


def reading_texts(draft):
    return [draft[k] for k in (*PEOPLE_FIELDS, *AXIS_KEYS)]


def reading_problems(draft, basis, type_id, input_text, base_texts):
    """(kind, fix) pairs in the same shape as checks.find_problems. Kinds are prefixed
    `reading_` so a reading that is still wrong after the repair drops only itself."""
    problems = []
    for field in (*PEOPLE_FIELDS, *AXIS_KEYS):
        limit = PERSON_MAX if field in PEOPLE_FIELDS else AXIS_MAX
        if not draft[field].strip() or len(draft[field]) > limit:
            problems.append(
                ("length", f"reading.{field}가 {len(draft[field])}자다. 1~{limit}자로 쓴다.")
            )
    problems += text_problems(reading_texts(draft), type_id, input_text)
    if PERSON_LETTER.search(" ".join([*base_texts, *reading_texts(draft)])):
        problems.append(("person_letter", "A, B 대신 '첫 번째 분', '두 번째 분'으로 쓴다."))
    stems = basis.caller_stems()
    if stems[0] != stems[1]:
        for field, own, other in zip(PEOPLE_FIELDS, stems, reversed(stems), strict=True):
            if other in draft[field] and own not in draft[field]:
                problems.append((
                    "person_swap",
                    f"{field}는 일간이 {own}인 사람이다. 두 사람 풀이가 뒤바뀌지 않게 다시 쓴다.",
                ))
    return [(f"reading_{kind}", fix) for kind, fix in problems]


def finalize_reading(draft, remaining=()):
    """Draft → public Reading (already in person_a / person_b order), or None."""
    if not draft or {f"reading_{k}" for k in HARD | {"length", "person_swap"}} & set(remaining):
        return None
    try:
        return Reading(
            people=[draft[k] for k in PEOPLE_FIELDS], axes={k: draft[k] for k in AXIS_KEYS}
        )
    except (ValueError, TypeError):
        return None
