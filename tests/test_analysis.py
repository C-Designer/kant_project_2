import json
import secrets

import httpx
import pytest
from fastapi.testclient import TestClient
from lovecode.api import create_app
from lovecode.contracts import TAXONOMY, demo_result
from lovecode.provider import OpenAIProvider
from lovecode.service import AnalysisService
from lovecode.settings import settings


@pytest.fixture
def live_config(monkeypatch):
    for key, value in {
        "api_enabled": True,
        "real_analysis_enabled": True,
        "provider": "openai",
        "api_key": "test-only",
        "model": "mock-responses",
        "classifier_mode": "openai",
        "rate_limit_enabled": False,
        "daily_analysis_limit": 20,
    }.items():
        monkeypatch.setattr(settings(), key, value)


def request_body(consent=True):
    return {
        "person_a": {
            "gender": "male",
            "birth_date": "1994-06-15",
            "birth_time": None,
            "mbti": "INTJ",
        },
        "person_b": {
            "gender": "female",
            "birth_date": "1996-09-20",
            "birth_time": "14:30",
            "mbti": "ENFP",
        },
        "external_processing_consent": consent,
    }


def response(data):
    return httpx.Response(
        200,
        json={
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": json.dumps(data, ensure_ascii=False)}
                    ],
                }
            ],
        },
    )


def mock_provider(type_id="T01", calls=None):
    def handle(r):
        body = json.loads(r.content)
        if calls is not None:
            calls.append(body)
        prompt = body["input"][1]["content"]
        assert "1994-06-15" not in prompt and "14:30" not in prompt and "1996-09-20" not in prompt
        assert body["store"] is False
        if "type_id" in body["text"]["format"]["schema"]["properties"]:
            return response({"type_id": type_id, "label_reason": "검증용 모의 응답"})
        return response(
            demo_result().model_dump(
                include={"summary", "strengths", "adjustments", "conversation_tip"}
            )
        )

    return OpenAIProvider(httpx.MockTransport(handle))


@pytest.mark.parametrize("type_id", list(TAXONOMY))
def test_all_types_analysis_share_delete(client, engine, live_config, type_id):
    # Same real HTTP route and real PostgreSQL store; only OpenAI transport is simulated.
    service = AnalysisService(provider=mock_provider(type_id))
    with TestClient(create_app(engine, analysis_service=service)) as c:
        r = c.post("/api/v1/analyses", json=request_body())
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        assert result["type_id"] == type_id and result["axes"] == TAXONOMY[type_id]["axes"]
        assert result["evidence_status"] == "ai_draft_unreviewed"
        keys = {"read_token": secrets.token_urlsafe(32), "delete_token": secrets.token_urlsafe(32)}
        saved = c.post("/api/v1/results", json={"save_ticket": r.json()["save_ticket"], **keys})
        assert saved.status_code == 201
        headers = {"Authorization": "Bearer " + keys["read_token"]}
        assert c.get("/api/v1/results", headers=headers).json()["result"] == result
        assert (
            c.delete(
                "/api/v1/results/" + saved.json()["result_id"],
                headers={"Authorization": "Bearer " + keys["delete_token"]},
            ).status_code
            == 204
        )
        assert c.get("/api/v1/results", headers=headers).status_code == 404


def test_no_consent_no_provider_calls(engine, live_config):
    calls = []
    with TestClient(create_app(engine, AnalysisService(mock_provider(calls=calls)))) as c:
        assert c.get("/api/v1/health").json()["analysis_ready"]
        assert c.post("/api/v1/analyses", json=request_body(False)).status_code == 422
    assert calls == []


@pytest.mark.parametrize("status", [401, 429, 500])
def test_provider_failure_no_save_ticket(engine, live_config, status):
    calls = []

    def fail(r):
        calls.append(r)
        return httpx.Response(status, text="secret details must not leak")

    with TestClient(
        create_app(engine, AnalysisService(OpenAIProvider(httpx.MockTransport(fail))))
    ) as c:
        r = c.post("/api/v1/analyses", json=request_body())
        assert r.status_code == 502
        assert "save_ticket" not in r.text and "secret" not in r.text
        assert len(calls) == 1


def test_daily_budget_and_deployment_origin(engine, live_config, monkeypatch):
    monkeypatch.setattr(settings(), "daily_analysis_limit", 1)
    monkeypatch.setattr(settings(), "allowed_origins", "https://lovecode.example")
    with TestClient(create_app(engine, AnalysisService(mock_provider()))) as c:
        assert (
            c.post(
                "/api/v1/analyses", json=request_body(), headers={"Origin": "https://evil.example"}
            ).status_code
            == 403
        )
        assert (
            c.post(
                "/api/v1/analyses",
                json=request_body(),
                headers={"Origin": "https://lovecode.example"},
            ).status_code
            == 200
        )
        assert c.post("/api/v1/analyses", json=request_body()).status_code == 429
