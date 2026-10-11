"""Fixed KST policy; lunar-python solar terms use UTC+8, local day/hour use UTC+9.
This adapter is experimental pending independent full-range validation.
"""

from datetime import datetime, timedelta

from lunar_python import Solar

from .contracts import Person

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
ELEMENTS = dict(
    zip(
        STEMS + BRANCHES,
        [
            "wood",
            "wood",
            "fire",
            "fire",
            "earth",
            "earth",
            "metal",
            "metal",
            "water",
            "water",
            "water",
            "earth",
            "wood",
            "wood",
            "earth",
            "fire",
            "fire",
            "earth",
            "metal",
            "metal",
            "earth",
            "water",
        ],
    )
)
VERSION = "fixed-kst-term-minus1h-day00-v1/lunar-python1.4.8"


def chart(dt):
    local = Solar.fromDate(dt).getLunar().getEightChar()
    local.setSect(2)
    term = Solar.fromDate(dt - timedelta(hours=1)).getLunar().getEightChar()
    day = local.getDay()
    branch = ((dt.hour + 1) // 2) % 12
    hour = STEMS[((STEMS.index(day[0]) % 5) * 2 + branch) % 10] + BRANCHES[branch]
    return {
        "year_pillar": term.getYear(),
        "month_pillar": term.getMonth(),
        "day_pillar": day,
        "hour_pillar": hour,
    }


def facts(person: Person):
    d = person.birth_date
    if person.birth_time is None:
        start = chart(datetime(d.year, d.month, d.day, 0, 0))
        end = chart(datetime(d.year, d.month, d.day, 23, 59, 59))
        f = {
            k: (start[k] if start[k] == end[k] else None)
            for k in ("year_pillar", "month_pillar", "day_pillar")
        }
        f["hour_pillar"] = None
        f["pillar_candidates"] = {
            k: [start[k], end[k]] for k in ("year_pillar", "month_pillar") if start[k] != end[k]
        }
    else:
        h, m = map(int, person.birth_time.split(":"))
        f = chart(datetime(d.year, d.month, d.day, h, m))
        f["pillar_candidates"] = {}
    f["day_master"] = f["day_pillar"][0]
    f["element_distribution"] = {
        e: sum(
            ELEMENTS[c] == e
            for k in ("year_pillar", "month_pillar", "day_pillar", "hour_pillar")
            for c in (f[k] or "")
        )
        for e in ("wood", "fire", "earth", "metal", "water")
    }
    f["strength"] = "unknown"
    f["needed_elements"] = "unknown"
    f["mbti"] = person.mbti
    f["missing_hour"] = person.birth_time is None
    return f


def input_text(a: Person, b: Person):
    import json

    # Canonical pair ordering guarantees the same representation after swapping A/B.
    texts = sorted(json.dumps(facts(p), ensure_ascii=False, sort_keys=True) for p in (a, b))
    return "가상 인물 1: " + texts[0] + "\n가상 인물 2: " + texts[1]
