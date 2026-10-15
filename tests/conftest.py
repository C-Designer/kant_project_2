import hashlib
import json
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from lovecode.api import create_app
from lovecode.settings import settings

MBTIS = [a + b + c + d for a in "EI" for b in "SN" for c in "TF" for d in "JP"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings(), "rate_limit_enabled", False)
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture(autouse=True)
def offline_api_boundary(monkeypatch):
    """A future real .env key must never turn this test suite into paid traffic."""
    import httpx

    monkeypatch.setattr(settings(), "api_enabled", False)
    monkeypatch.setattr(settings(), "real_analysis_enabled", False)
    monkeypatch.setattr(settings(), "share_secret", "")

    def reject_network(*args, **kwargs):
        raise AssertionError("Real HTTP requests are forbidden in offline tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", reject_network)


def build_fixture_dataset(dest, sizes=(48, 16, 16), seed=7):
    """Small unlabeled dataset in the couples.csv contract (compact-v5 text, disjoint pairs).

    Large enough for every split to carry all 16 labels once a test assigns them; never shipped.
    """
    from lovecode.contracts import Person
    from lovecode.dataset import HEADERS, write_csv
    from lovecode.features import VERSION, compact_text

    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    splits = [s for s, n in zip(("train", "validation", "test"), sizes, strict=True) for _ in range(n)]
    people, pairs, rows = [], [], []
    for i, split in enumerate(splits):
        persons, ids = [], []
        for j in range(2):
            known = rng.random() >= 0.2
            person = Person(
                gender=rng.choice(["male", "female", "unspecified"]),
                birth_date=date(1960, 1, 1) + timedelta(days=rng.randrange(16437)),
                birth_time=f"{rng.randrange(24):02}:{rng.randrange(60):02}" if known else None,
                mbti=rng.choice(MBTIS),
            )
            pid = f"P{2 * i + j + 1:04}"
            ids.append(pid)
            persons.append(person)
            people.append(
                {"person_id": pid, **person.model_dump(mode="json"), "source": "synthetic", "seed": seed}
            )
        text, _ = compact_text(*persons)
        cid, gid = f"C{i + 1:04}", f"G{i + 1:04}"
        pairs.append({"couple_id": cid, "group_id": gid, "person_a_id": ids[0], "person_b_id": ids[1]})
        rows.append(dict(zip(HEADERS, [cid, gid, text, "", "", "pending", split], strict=True)))
    write_csv(dest / "couples.csv", rows)
    (dest / "synthetic_people.json").write_text(json.dumps(people, ensure_ascii=False), encoding="utf-8")
    (dest / "synthetic_pairs.json").write_text(json.dumps(pairs, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "dataset_version": "test-fixture",
        "source": "synthetic",
        "seed": seed,
        "count": len(rows),
        "train_size_experiment": True,
        "splits": dict(Counter(splits)),
        "calendar_version": VERSION,
        "text_format": "compact-v5",
        "human_review": "incomplete",
        "taxonomy_version": "love-code-v1",
        "input_sha256": hashlib.sha256("".join(r["input_text"] for r in rows).encode()).hexdigest(),
    }
    (dest / "dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (dest / "annotation_records.jsonl").touch()
    return dest


@pytest.fixture
def synthetic_dataset(tmp_path):
    return build_fixture_dataset(tmp_path / "data")
