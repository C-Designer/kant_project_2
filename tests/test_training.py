"""Fixture labels/encoder verify execution only; never claim model quality."""

import csv
import hashlib
import json
import shutil
from types import SimpleNamespace

import httpx
import pytest
from lovecode.annotate import annotate
from lovecode.contracts import TAXONOMY
from lovecode.dataset import write_csv
from lovecode.inference import ArtifactError, Classifier
from lovecode.provider import OpenAIProvider, ProviderError
from lovecode.settings import settings
from lovecode.train import train


class FixtureEncoder:
    def __init__(self, *args, **kwargs):
        from sklearn.feature_extraction.text import HashingVectorizer

        self.vectorizer = HashingVectorizer(
            n_features=128, analyzer="char", ngram_range=(2, 3), alternate_sign=False
        )

    def encode(self, texts, **kwargs):
        return self.vectorizer.transform(texts).toarray()


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
    rows = list(csv.DictReader((dataset / "couples.csv").open()))
    assert sum(bool(r["label"]) for r in rows) == 1
    assert rows[0]["review_status"] == "pending"
    args.max_calls = 1
    annotate(args, provider=OpenAIProvider(httpx.MockTransport(handle)))
    rows = list(csv.DictReader((dataset / "couples.csv").open()))
    assert sum(bool(r["label"]) for r in rows) == 2
    assert all(r["review_status"] == "pending" for r in rows)
    assert len(calls) == 3  # successful checkpoint is not paid again


def test_real_estimators_fixture_data_and_artifact_guards(dataset, tmp_path):
    rows = list(csv.DictReader((dataset / "couples.csv").open()))
    labels = [v["label"] for v in TAXONOMY.values()]
    counters = {}
    for r in rows:
        n = counters.get(r["split"], 0)
        r.update(label=labels[n % 16], label_reason="모의 학습 배선 검증 전용, 정답 아님")
        counters[r["split"]] = n + 1
    write_csv(dataset / "couples.csv", rows)
    args = SimpleNamespace(
        dir=dataset,
        allow_ai_drafts=True,
        dry_run=False,
        encoder="fixture-hashing",
        encoder_revision="fixture",
        output=tmp_path / "models",
        fixture=True,
    )
    report = train(args, encoder_factory=FixtureEncoder)
    assert report["fixture"] is True and report["human_review"] == "incomplete"
    assert set(report["candidates"]) == {"tfidf_lr", "pretrained_encoder_lr"}
    assert len(report["test"]["confusion_matrix"]) == 16
    with pytest.raises(ArtifactError, match="FIXTURE"):
        Classifier(args.output)
    model = Classifier(args.output, allow_fixture=True, encoder_factory=FixtureEncoder)
    assert model.predict(rows[0]["input_text"]) in TAXONOMY
    name = "tfidf_lr.joblib" if report["selected"] == "tfidf_lr" else "encoder_lr.joblib"
    (args.output / name).write_bytes(b"tampered")
    with pytest.raises(ArtifactError, match="DIGEST"):
        Classifier(args.output, allow_fixture=True, encoder_factory=FixtureEncoder)
    assert (
        report["csv_sha256"] == hashlib.sha256((dataset / "couples.csv").read_bytes()).hexdigest()
    )
    with open("data/synthetic-v1/couples.csv") as f:
        assert not any(r["label"] for r in csv.DictReader(f))


def test_unlabeled_training_blocked(dataset, tmp_path):
    args = SimpleNamespace(
        dir=dataset,
        allow_ai_drafts=True,
        dry_run=False,
        encoder_revision="a" * 40,
        output=tmp_path / "models",
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


def test_training_rejects_unsupported_birthday_before_fit(dataset, tmp_path):
    source = dataset / "synthetic_people.json"
    people = json.loads(source.read_text())
    people[0]["birth_date"] = "1939-12-31"
    source.write_text(json.dumps(people))
    args = SimpleNamespace(dir=dataset, output=tmp_path / "models")
    with pytest.raises(ValueError, match="1940"):
        train(args)
    assert not args.output.exists()
