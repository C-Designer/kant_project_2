"""Checks on the live calendar (backend/lovecode/saju), the only one the service and data use."""

import random
from datetime import date, timedelta

from korean_lunar_calendar import KoreanLunarCalendar
from lovecode.saju.manse import calc_saju


def test_day_pillar_matches_independent_library_120_cases():
    rng = random.Random(17)
    k = KoreanLunarCalendar()
    for _ in range(120):
        d = date(1940, 1, 1) + timedelta(days=rng.randrange(32500))
        assert k.setSolarDate(d.year, d.month, d.day)
        expected = k.getChineseGapJaString().split()[2][:2]
        assert calc_saju(d.year, d.month, d.day, 12, 0).day == expected


def test_late_evening_birth_belongs_to_the_next_day():
    # Team convention sect=1 (docs/labeling/calc_convention.md): 23:00-23:59 takes the next
    # day's pillar; the hour pillar is that day's 子 hour.
    late = calc_saju(2024, 2, 3, 23, 30)
    assert late.day == calc_saju(2024, 2, 4, 12, 0).day == "戊戌"
    assert late.time == calc_saju(2024, 2, 4, 0, 10).time == "壬子"
    assert calc_saju(2024, 2, 3, 22, 30).day == "丁酉"


def test_term_boundary_and_unknown_hour():
    # Adapter regression against lunar-python's 2024 입춘 (16:27 UTC+8 = 17:27 KST); this is
    # not an independent astronomical check.
    assert calc_saju(2024, 2, 4, 17, 26).year == "癸卯"
    assert calc_saju(2024, 2, 4, 17, 28).year == "甲辰"
    unknown = calc_saju(2024, 2, 4)
    assert unknown.time is None and not unknown.time_known
    assert any("입춘" in note for note in unknown.notes)
