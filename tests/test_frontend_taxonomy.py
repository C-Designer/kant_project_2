"""The illustrated guide must agree with the API's authoritative taxonomy."""

import json
from pathlib import Path

from lovecode.contracts import AXIS_KEYS, TAXONOMY


def test_frontend_guide_covers_backend_types_without_changing_axes():
    root = Path(__file__).resolve().parents[1]
    guide = json.loads((root / "frontend/data/relationship-types.json").read_text(encoding="utf-8"))
    assert len(guide) == len(TAXONOMY)
    assert {item["id"] for item in guide} == set(TAXONOMY)
    assert len({item["slug"] for item in guide}) == len(guide)
    for item in guide:
        canonical = TAXONOMY[item["id"]]
        assert item["axes"] == [canonical["axes"][key] for key in AXIS_KEYS]
        assert "·".join(item["labels"]) == canonical["label"]
        assert (root / "frontend/public" / item["image"].lstrip("/")).is_file()
        crop = item["crop"]
        assert 0 <= crop["x"] < crop["x"] + crop["width"] <= 1024
        assert 0 <= crop["y"] < crop["y"] + crop["height"] <= 1536


def test_frontend_guide_pages_have_full_reading_content():
    root = Path(__file__).resolve().parents[1]
    guide = json.loads((root / "frontend/data/relationship-types.json").read_text(encoding="utf-8"))
    lists = ("strengths", "cares", "conflict", "dates", "tips")
    for item in guide:
        assert item["day"].strip()
        for key in lists:
            assert len(item[key]) == 3 and len(set(item[key])) == 3, (item["id"], key)
        texts = [item["day"], *(t for key in lists for t in item[key])]
        assert not any(w in t for t in texts for w in ("반드시", "무조건", "운명")), item["id"]
