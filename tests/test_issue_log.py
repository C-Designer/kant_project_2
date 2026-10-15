"""Issue log: failures are classified and correlated, and never carry user input or secrets."""

import json
import logging

import httpx
import pytest
from fastapi.testclient import TestClient
from lovecode.api import create_app
from lovecode.provider import OpenAIProvider
from lovecode.service import AnalysisService
from lovecode.settings import settings
from test_analysis import mock_provider, request_body

SENTINELS = ["1994-06-15", "1996-09-20", "14:30", "INTJ", "ENFP", "sk-fixture-key", "<!channel>"]


@pytest.fixture
def records():
    seen = []

    class Collect(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())

    log = logging.getLogger("lovecode.issue")
    handler = Collect()
    log.addHandler(handler)
    yield seen
    log.removeHandler(handler)


@pytest.fixture
def real_mode(monkeypatch):
    for key, value in {
        "api_enabled": True, "real_analysis_enabled": True, "provider": "openai",
        "api_key": "sk-fixture-key", "model": "mock", "classifier_mode": "openai",
        "rate_limit_enabled": False,
    }.items():
        monkeypatch.setattr(settings(), key, value)


def quota_exhausted(r):
    return httpx.Response(
        429,
        headers={"x-request-id": "req_fixture123", "x-ratelimit-remaining-requests": "0"},
        json={"error": {
            "type": "insufficient_quota", "code": "insufficient_quota",
            "message": "quota <!channel> 1994-06-15 INTJ sk-fixture-key",
        }},
    )


def test_provider_429_is_classified_and_correlated(real_mode, records):
    service = AnalysisService(OpenAIProvider(httpx.MockTransport(quota_exhausted)))
    with TestClient(create_app(analysis_service=service)) as client:
        r = client.post(
            "/api/v1/analyses", json=request_body(),
            headers={"x-vercel-id": "icn1::abc12-1700000000000-deadbeef"},
        )
    assert r.status_code == 502
    request_id = r.headers["X-Request-ID"]
    assert request_id == "icn1::abc12-1700000000000-deadbeef" == r.json()["request_id"]

    errors = [json.loads(m) for m in records if '"analysis.provider_failed"' in m]
    assert len(errors) == 1
    rec = errors[0]
    assert rec["level"] == "error" and rec["request_id"] == request_id
    assert rec["http_status"] == 429
    assert rec["provider_error_code"] == "insufficient_quota"
    assert rec["provider_request_id"] == "req_fixture123"
    assert rec["fingerprint"] == "analysis.provider_failed:PROVIDER_REQUEST_FAILED:insufficient_quota"
    for line in records:
        for sentinel in SENTINELS:
            assert sentinel not in line


def test_success_and_unsafe_inbound_id(real_mode, records):
    with TestClient(create_app(analysis_service=AnalysisService(mock_provider("T13")))) as client:
        r = client.post(
            "/api/v1/analyses", json=request_body(), headers={"x-vercel-id": "bad id\n<script>"}
        )
    assert r.status_code == 200
    request_id = r.headers["X-Request-ID"]
    assert len(request_id) == 32 and request_id.isalnum()  # minted, not the client's value
    done = [json.loads(m) for m in records if '"analysis.completed"' in m]
    assert done and done[0]["request_id"] == request_id and done[0]["level"] == "info"
    assert all(s not in line for line in records for s in SENTINELS)


def test_unhandled_error_is_logged_with_request_id(real_mode, records):
    class Broken(AnalysisService):
        def analyse(self, body):
            raise RuntimeError("1994-06-15 should never be logged")

    with TestClient(create_app(analysis_service=Broken(mock_provider())), raise_server_exceptions=False) as client:
        r = client.post("/api/v1/analyses", json=request_body())
    assert r.status_code == 500 and r.json()["request_id"] == r.headers["X-Request-ID"]
    rec = json.loads(next(m for m in records if '"request.unhandled"' in m))
    assert rec["exception"] == "RuntimeError" and "1994" not in json.dumps(rec)
