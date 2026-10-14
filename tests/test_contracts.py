from datetime import date

import pytest
from lovecode.contracts import TAXONOMY, Person, PublicResult, demo_result


def person(d="2024-02-04", t=None):
    return Person(gender="unspecified", birth_date=d, birth_time=t, mbti="INTP")


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
