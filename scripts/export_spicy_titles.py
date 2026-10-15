"""Write frontend/data/spicy-titles.json from lovecode.spicy (tests fail if it drifts).

uv run python scripts/export_spicy_titles.py
"""

import json
from pathlib import Path

from lovecode.contracts import TAXONOMY
from lovecode.spicy import TITLES, TOPICS, reachable_titles

TOPIC_LABELS = {
    "skinship": {"emoji": "🔥", "name": "속궁합"},
    "temptation": {"emoji": "👀", "name": "바람기 · 유혹 내성"},
    "jealousy": {"emoji": "🔒", "name": "질투 · 집착"},
    "reunion": {"emoji": "💔", "name": "전 애인 미련 · 재회"},
}
OUT = Path(__file__).resolve().parents[1] / "frontend/data/spicy-titles.json"


def build():
    return {
        "topics": [{"key": t, **TOPIC_LABELS[t]} for t in TOPICS],
        "titles": TITLES,
        "reachable": {type_id: reachable_titles(type_id) for type_id in TAXONOMY},
    }


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUT)
