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
