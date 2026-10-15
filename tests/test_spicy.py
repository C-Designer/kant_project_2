"""매운맛 궁합 칭호 규칙 (docs/SPICY_SPEC.md §2, §7 인수 조건 1~4·12)."""

from itertools import product

import pytest
from lovecode.contracts import TAXONOMY
from lovecode.saju import build_person
from lovecode.saju.spicy import has_doha, has_hongyeom, spicy_signals
from lovecode.spicy import (
    RULES,
    SIGNALS,
    TITLES,
    TOPICS,
    pick_titles,
    reachable_titles,
    spicy_text_ok,
)


def chart(year, month, day, time=None):
    return {
        "year": year,
        "month": month,
        "day": day,
        "time": time,
        "pillars": [year, month, day, time],
    }


@pytest.mark.parametrize(
    ("saju", "expected"),
    [
        (chart("甲子", "丙寅", "庚午", "乙酉"), True),  # 년지 子 → 酉가 시지에
        (chart("甲寅", "丁卯", "庚午", None), True),  # 년지 寅 → 卯가 월지에
        (chart("甲寅", "丙寅", "壬午", "丁卯"), True),  # 일지 午 → 卯가 시지에
        (chart("乙亥", "戊子", "辛未", None), True),  # 년지 亥 → 子가 월지에
        (chart("甲子", "丙寅", "庚午", None), False),  # 시주 없음 → 酉 없음
        (chart("癸巳", "甲寅", "丙辰", "己亥"), False),
    ],
)
def test_doha_table(saju, expected):
    assert has_doha(saju) is expected


@pytest.mark.parametrize(
    ("saju", "expected"),
    [
        (chart("甲子", "丙寅", "甲午", None), True),  # 甲 → 午
        (chart("甲寅", "丙寅", "丙申", None), True),  # 丙 → 寅
        (chart("甲子", "丁未", "辛卯", "丁酉"), True),  # 辛 → 酉
        (chart("甲子", "丙寅", "癸亥", None), False),  # 癸 → 申 없음
    ],
)
def test_hongyeom_table(saju, expected):
    assert has_hongyeom(saju) is expected


def test_signals_are_swap_invariant_on_real_charts():
    a = build_person("F", 1995, 3, 14, 9, 30, "ENFP")
    b = build_person("M", 1993, 11, 2, None, None, "ISTJ")
    assert spicy_signals(a, b) == spicy_signals(b, a)
    assert set(spicy_signals(a, b)) == set(SIGNALS)


def test_signals_ignore_gender():
    a = build_person("F", 1995, 3, 14, 9, 30, "ENFP")
    a_u = build_person("U", 1995, 3, 14, 9, 30, "ENFP")
    b = build_person("M", 1993, 11, 2, None, None, "ISTJ")
    assert spicy_signals(a, b) == spicy_signals(a_u, b)


def test_every_type_and_signal_combo_gets_one_title_per_topic():
    for type_id, values in product(TAXONOMY, product((False, True), repeat=len(SIGNALS))):
        titles = pick_titles(dict(zip(SIGNALS, values)), type_id)
        assert set(titles) == set(TOPICS)
        for topic, title in titles.items():
            assert title["id"] in {tid for _, tid in RULES[topic]}
            assert title["text"] == TITLES[title["id"]]


def test_every_title_is_reachable():
    reached = {tid for t in TAXONOMY for ids in reachable_titles(t).values() for tid in ids}
    assert reached == set(TITLES)


def test_reachable_titles_follow_axes():
    # 독립형(T: distance=independent)은 J1·J2(밀착형 전용)가 나올 수 없다.
    independent = next(t for t, v in TAXONOMY.items() if v["axes"]["distance"] == "independent")
    assert not {"J1", "J2"} & set(reachable_titles(independent)["jealousy"])


@pytest.mark.parametrize("title_id", sorted(TITLES))
def test_fixed_titles_pass_the_spicy_checker(title_id):
    assert spicy_text_ok(TITLES[title_id])


@pytest.mark.parametrize(
    "text",
    [
        "둘이 잠자리 궁합은 최고야",  # 19금
        "체위 얘기는 따로 해 봐",
        "씨발 이건 좀 아니다",  # 욕설 원형
        "존나 잘 맞아",
        "바람 확률 87%인 커플",  # 퍼센트·확률
        "속궁합 1등급",
        "반드시 헤어질 운명이야",  # 단정
        "ENFP라서 그래",  # 기존 공통 금지
        "x" * 141,  # 길이
        "",
    ],
)
def test_spicy_checker_rejects(text):
    assert not spicy_text_ok(text)


@pytest.mark.parametrize(
    "text", ["속궁합은 ㅈㄴ 뜨거운 편", "바람기 걱정보다 질투가 개빡셈", "미쳤다 이 케미"]
)
def test_spicy_checker_allows_topic_words_and_softened_slang(text):
    assert spicy_text_ok(text)
