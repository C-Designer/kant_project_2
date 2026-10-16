"""'왜 이 유형일까' reading: rule evidence per axis and person order (lovecode.reading)."""

import re

import pytest
from lovecode.checks import opposite_poles, poles
from lovecode.contracts import AXIS_KEYS, TAXONOMY, Person
from lovecode.features import analysis_inputs
from lovecode.labeler import AXES
from lovecode.reading import (
    axis_evidence,
    finalize_reading,
    names,
    reading_problems,
    reading_prompt,
)

A = Person(gender="female", birth_date="1997-03-14", birth_time="08:30", mbti="ENFP")
B = Person(gender="male", birth_date="1995-11-02", birth_time=None, mbti="ISTJ")


def draft(**changes):
    return {
        "first_person": "나무 기운의 분이에요.",
        "second_person": "불 기운의 분이에요.",
        "chemistry": "서로 채워 줘요.",
        "temperature": "꾸준해요.",
        "distance": "함께해요.",
        "conflict": "대화로 풀어요.",
        **changes,
    }


def test_names_and_day_stems_follow_the_callers_order_whichever_way_round():
    ab, ba = analysis_inputs(A, B), analysis_inputs(B, A)
    # Same narrative either way round; only the A/B → caller mapping flips.
    assert ab["narrative"] == ba["narrative"]
    assert ab["basis"].swapped != ba["basis"].swapped
    assert names(ab["basis"]) == tuple(reversed(names(ba["basis"])))
    # A (1997-03-14) is 을목, B (1995-11-02) is 정화, whatever the canonical order.
    assert ab["basis"].caller_stems() == ("을목", "정화")
    assert ba["basis"].caller_stems() == ("정화", "을목")
    prompt = reading_prompt(ab["basis"], "T01")
    assert "'첫 번째 분'(입력의 " in prompt and "일간 을목)이 어떤 사람인지" in prompt


def test_swapped_person_readings_are_caught_and_dropped():
    basis = analysis_inputs(A, B)["basis"]
    good = draft(first_person="을목 일간이라 유연해요.", second_person="정화 일간이라 따뜻해요.")
    bad = draft(first_person="정화 일간이라 따뜻해요.", second_person="을목 일간이라 유연해요.")
    assert not reading_problems(good, basis, "T01", "", [])
    assert {k for k, _ in reading_problems(bad, basis, "T01", "", [])} == {"reading_person_swap"}
    assert finalize_reading(bad, ["reading_person_swap"]) is None
    assert finalize_reading(good).people == [good["first_person"], good["second_person"]]


@pytest.mark.parametrize("type_id", list(TAXONOMY))
def test_evidence_names_only_the_chosen_poles(type_id):
    basis = analysis_inputs(A, B)["basis"]
    text = axis_evidence(basis, type_id)
    for pole in poles(type_id):
        assert f"- {pole} (" in text
    for other in opposite_poles(type_id):
        assert other not in text
    assert not re.search(r"[一-鿿]", reading_prompt(basis, type_id))


def test_evidence_lists_the_rule_signals_when_the_classifier_agrees():
    basis = analysis_inputs(A, B)["basis"]
    text = axis_evidence(basis, basis.rule["type_id"])
    assert "분류 모델이" not in text
    for axis, (first, second) in AXES.items():
        pole = (first, second).index(basis.rule[axis])
        for reason in basis.rule["signals"][axis]["saju"][pole]:
            assert reason in text


def test_evidence_admits_when_the_classifier_overrode_the_rules():
    basis = analysis_inputs(A, B)["basis"]
    index = int(basis.rule["type_id"][1:]) - 1
    other = f"T{(index ^ 0b1000) + 1:02}"  # chemistry is the leading bit of the type index
    text = axis_evidence(basis, other)
    chemistry, *rest = text.split("\n- ")
    assert "분류 모델이 두 사람 데이터 전체 흐름" in chemistry
    assert not any("분류 모델이" in block for block in rest)


def test_reading_problems_are_prefixed_and_catch_letters_and_codes():
    basis = analysis_inputs(A, B)["basis"]
    kinds = {k for k, _ in reading_problems(draft(first_person="A님은 INTJ"), basis, "T01", "", [])}
    assert {"reading_mbti_code", "reading_person_letter"} <= kinds
    assert {k for k, _ in reading_problems(draft(), basis, "T01", "", [])} == set()
    too_long = reading_problems(draft(distance="가" * 221), basis, "T01", "", [])
    assert [k for k, _ in too_long] == ["reading_length"]


def test_a_reading_still_wrong_after_repair_is_dropped_alone():
    assert finalize_reading(draft(), ["opposite_pole"]) is not None
    assert finalize_reading(draft(), ["reading_person_letter"]) is not None
    assert finalize_reading(draft(), ["reading_hanja"]) is None
    assert finalize_reading(draft(), ["reading_length"]) is None
    assert finalize_reading(draft(conflict="ENFP라서")) is None
    assert set(finalize_reading(draft()).axes) == set(AXIS_KEYS)
