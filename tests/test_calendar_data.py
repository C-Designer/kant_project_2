import random
from datetime import date, datetime, timedelta

import pytest
from korean_lunar_calendar import KoreanLunarCalendar
from lovecode.calendar import chart, facts, input_text
from lovecode.contracts import TAXONOMY, Person, PublicResult, demo_result
from lovecode.dataset import validate


def person(d="2024-02-04", t=None):
    return Person(gender="unspecified", birth_date=d, birth_time=t, mbti="INTP")


def test_day_independent_library_120_cases():
    rng = random.Random(17)
    k = KoreanLunarCalendar()
    for _ in range(120):
        d = date(1900, 1, 1) + timedelta(days=rng.randrange(45940))
        assert k.setSolarDate(d.year, d.month, d.day)
        expected = k.getChineseGapJaString().split()[2][:2]
        assert chart(datetime(d.year, d.month, d.day, 12))["day_pillar"] == expected


def test_term_timezone_and_unknown_candidates():
    # Library's term calculation is 16:27:07 UTC+8; fixed KST is 17:27:07.
    # This is an adapter regression fixture, NOT independent astronomical validation.
    assert chart(datetime(2024, 2, 4, 17, 26))["year_pillar"] == "癸卯"
    assert chart(datetime(2024, 2, 4, 17, 28))["year_pillar"] == "甲辰"
    f = facts(person())
    assert f["hour_pillar"] is None
    assert f["year_pillar"] is None
    assert f["pillar_candidates"]["year_pillar"] == ["癸卯", "甲辰"]
    assert facts(person("2024-02-05"))["year_pillar"] == "甲辰"


def test_midnight_day_hour_policy():
    before = chart(datetime(2024, 2, 3, 23, 30))
    after = chart(datetime(2024, 2, 4, 0, 0))
    assert before["day_pillar"] == "丁酉"
    assert after["day_pillar"] == "戊戌"
    assert before["hour_pillar"] == "庚子"
    assert after["hour_pillar"] == "壬子"
    assert chart(datetime(2024, 2, 4, 1, 0))["hour_pillar"] == "癸丑"


def test_pair_swap_and_no_invented_hour():
    a = person("1993-01-10", None)
    b = person("1995-08-20", "00:00")
    assert input_text(a, b) == input_text(b, a)
    assert facts(a)["hour_pillar"] is None
    assert facts(b)["hour_pillar"] is not None


def test_taxonomy_and_public_guards():
    assert len(TAXONOMY) == 16
    assert len({v["label"] for v in TAXONOMY.values()}) == 16
    v = demo_result().model_dump()
    v["type_id"] = "T01"
    with pytest.raises(ValueError):
        PublicResult.model_validate(v)
    v = demo_result().model_dump()
    v["summary"] = "INTP의 연애"
    with pytest.raises(ValueError):
        PublicResult.model_validate(v)


def test_dataset_contract():
    report = validate("data/synthetic-v1")
    assert report["rows"] == 600 and report["cross_split_people"] == 0
    assert report["approved"] == 0 and report["labeled"] == 0


@pytest.mark.parametrize(
    "change",
    [
        {"birth_date": "2024-02-30"},
        {"birth_time": "24:00"},
        {"birth_date": "1899-01-01"},
        {"birth_date": "1939-12-31"},
        {"birth_date": "2099-01-01"},
        {"mbti": "XXXX"},
    ],
)
def test_person_rejects_invalid(change):
    values = {
        "gender": "unspecified",
        "birth_date": "2000-01-01",
        "birth_time": None,
        "mbti": "INTP",
    }
    with pytest.raises(ValueError):
        Person(**(values | change))


def test_person_accepts_first_supported_birthday():
    assert person("1940-01-01").birth_date == date(1940, 1, 1)
