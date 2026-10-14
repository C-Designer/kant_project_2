"""Fixture labels verify execution only; never claim model quality."""

import csv
import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest
from lovecode.contracts import TAXONOMY
from lovecode.dataset import write_csv
from lovecode.inference import ArtifactError, Classifier
from lovecode.provider import OpenAIProvider, ProviderError
from lovecode.settings import settings
from lovecode.train import train


def read_rows(dataset):
    with (dataset / "couples.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


<<<<<<< HEAD
@pytest.fixture
def dataset(tmp_path):
    dest = tmp_path / "data"
    shutil.copytree("data/synthetic-v1", dest)
    return dest


def test_annotation_checkpoint_resume(dataset, monkeypatch):
    for key, value in {
        "api_enabled": True,
        "provider": "openai",
        "api_key": "fixture",
        "model": "fixture",
    }.items():
        monkeypatch.setattr(settings(), key, value)
    calls = []

    def handle(r):
        calls.append(r)
        if len(calls) == 2:
            return httpx.Response(429)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {"type_id": "T01", "label_reason": "모의 검증 전용"}
                                ),
                            }
                        ],
                    }
                ],
            },
        )

    args = SimpleNamespace(dir=dataset, max_calls=3, dry_run=False, allow_paid=True)
    with pytest.raises(SystemExit):
        annotate(args, provider=OpenAIProvider(httpx.MockTransport(handle)))
    rows = list(csv.DictReader((dataset / "couples.csv").open(encoding="utf-8")))
    assert sum(bool(r["label"]) for r in rows) == 1
    assert rows[0]["review_status"] == "pending"
    args.max_calls = 1
    annotate(args, provider=OpenAIProvider(httpx.MockTransport(handle)))
    rows = list(csv.DictReader((dataset / "couples.csv").open(encoding="utf-8")))
    assert sum(bool(r["label"]) for r in rows) == 2
    assert all(r["review_status"] == "pending" for r in rows)
    assert len(calls) == 3  # successful checkpoint is not paid again


def test_real_estimators_fixture_data_and_artifact_guards(dataset, tmp_path):
    rows = list(csv.DictReader((dataset / "couples.csv").open(encoding="utf-8")))
=======
def test_real_estimators_fixture_data_and_artifact_guards(synthetic_dataset, tmp_path):
    rows = read_rows(synthetic_dataset)
>>>>>>> origin/main
    labels = [v["label"] for v in TAXONOMY.values()]
    counters = {}
    for r in rows:
        n = counters.get(r["split"], 0)
        r.update(label=labels[n % 16], label_reason="모의 학습 배선 검증 전용, 정답 아님")
        counters[r["split"]] = n + 1
    write_csv(synthetic_dataset / "couples.csv", rows)
    args = SimpleNamespace(
        dir=synthetic_dataset,
        allow_ai_drafts=True,
        dry_run=False,
        output=tmp_path / "models",
        fixture=True,
    )
    report = train(args)
    assert report["fixture"] is True and report["human_review"] == "incomplete"
    assert set(report["candidates"]) == {"tfidf_lr"} and report["selected"] == "tfidf_lr"
    assert len(report["test"]["confusion_matrix"]) == 16
    with pytest.raises(ArtifactError, match="FIXTURE"):
        Classifier(args.output)
    model = Classifier(args.output, allow_fixture=True)
    assert model.predict(rows[0]["input_text"]) in TAXONOMY
    (args.output / "tfidf_lr.joblib").write_bytes(b"tampered")
    with pytest.raises(ArtifactError, match="DIGEST"):
<<<<<<< HEAD
        Classifier(args.output, allow_fixture=True, encoder_factory=FixtureEncoder)
    assert (
        report["csv_sha256"] == hashlib.sha256((dataset / "couples.csv").read_bytes()).hexdigest()
    )
    with open("data/synthetic-v1/couples.csv", encoding="utf-8") as f:
        assert not any(r["label"] for r in csv.DictReader(f))
=======
        Classifier(args.output, allow_fixture=True)
    csv_bytes = (synthetic_dataset / "couples.csv").read_bytes()
    assert report["csv_sha256"] == hashlib.sha256(csv_bytes).hexdigest()
>>>>>>> origin/main


def test_unlabeled_training_blocked(synthetic_dataset, tmp_path):
    args = SimpleNamespace(
        dir=synthetic_dataset, allow_ai_drafts=True, dry_run=False, output=tmp_path / "models"
    )
    with pytest.raises(ValueError, match="coverage"):
        train(args)
    assert not args.output.exists()


def test_timeout_and_malformed_envelope(monkeypatch):
    for key, value in {
        "api_enabled": True,
        "provider": "openai",
        "api_key": "fixture",
        "model": "fixture",
    }.items():
        monkeypatch.setattr(settings(), key, value)

    def timeout(r):
        raise httpx.ReadTimeout("secret input")

    with pytest.raises(ProviderError, match="PROVIDER_REQUEST_FAILED"):
        OpenAIProvider(httpx.MockTransport(timeout)).label("fixture", allow_paid=True)
    for payload in [[], {"status": "completed", "output": [None]}]:
        with pytest.raises(ProviderError, match="PROVIDER_REQUEST_FAILED"):
            OpenAIProvider(
                httpx.MockTransport(lambda r, payload=payload: httpx.Response(200, json=payload))
            ).label("fixture", allow_paid=True)


<<<<<<< HEAD
def test_training_rejects_unsupported_birthday_before_fit(dataset, tmp_path):
    source = dataset / "synthetic_people.json"
    people = json.loads(source.read_text(encoding="utf-8"))
    people[0]["birth_date"] = "1939-12-31"
    source.write_text(json.dumps(people), encoding="utf-8")
    args = SimpleNamespace(dir=dataset, output=tmp_path / "models")
=======
def test_training_rejects_unsupported_birthday_before_fit(synthetic_dataset, tmp_path):
    source = synthetic_dataset / "synthetic_people.json"
    people = json.loads(source.read_text())
    people[0]["birth_date"] = "1939-12-31"
    source.write_text(json.dumps(people))
    args = SimpleNamespace(dir=synthetic_dataset, output=tmp_path / "models")
>>>>>>> origin/main
    with pytest.raises(ValueError, match="1940"):
        train(args)
    assert not args.output.exists()
