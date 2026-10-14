import json

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
def test_all_types_analysis(live_config, type_id):
    # Real HTTP route; only OpenAI transport is simulated.
    service = AnalysisService(provider=mock_provider(type_id))
    with TestClient(create_app(analysis_service=service)) as c:
        r = c.post("/api/v1/analyses", json=request_body())
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        assert result["type_id"] == type_id and result["axes"] == TAXONOMY[type_id]["axes"]
        assert result["evidence_status"] == "ai_draft_unreviewed"
        assert set(r.json()) == {"analysis_id", "result"}


def test_no_consent_no_provider_calls(live_config):
    calls = []
    with TestClient(create_app(AnalysisService(mock_provider(calls=calls)))) as c:
        assert c.get("/api/v1/health").json()["analysis_ready"]
        assert c.post("/api/v1/analyses", json=request_body(False)).status_code == 422
    assert calls == []


def test_release_classifier_uses_training_text(live_config, monkeypatch):
    from lovecode.contracts import AnalysisInput
    from lovecode.features import compact_text

    monkeypatch.setattr(settings(), "classifier_mode", "local")
    inputs, calls = [], []

    class RecordingClassifier:
        def __init__(self):
            self.report = {"dataset": {"text_format": "compact-v5"}}

        def predict(self, text):
            inputs.append(text)
            return "T13"

    body = request_body()
    parsed = AnalysisInput.model_validate(body)
    expected, missing = compact_text(parsed.person_a, parsed.person_b)
    service = AnalysisService(mock_provider(calls=calls), RecordingClassifier())
    with TestClient(create_app(service)) as c:
        assert c.get("/api/v1/health").json()["analysis_ready"]
        first = c.post("/api/v1/analyses", json=body)
        assert first.status_code == 200
        result = first.json()["result"]
        assert result["type_id"] == "T13"
        assert result["axes"] == TAXONOMY["T13"]["axes"]
        assert result["limitations"] == missing
        body["person_a"], body["person_b"] = body["person_b"], body["person_a"]
        second = c.post("/api/v1/analyses", json=body)
        assert second.status_code == 200
        assert second.json()["result"]["type_id"] == "T13"
    assert inputs == [expected, expected]
    assert len(calls) == 2  # One explanation call each; no cloud classification.
    assert all("type_id" not in c["text"]["format"]["schema"]["properties"] for c in calls)


def test_classifier_and_explainer_share_one_saju(live_config, monkeypatch):
    # 23:38 birth: the team convention (sect=1) moves the day pillar to the next day.
    # The explainer must read the same charts as the classifier.
    from lovecode.contracts import AnalysisInput
    from lovecode.features import analysis_inputs, pair_text, to_saju_person

    monkeypatch.setattr(settings(), "classifier_mode", "local")
    inputs, calls = [], []

    class RecordingClassifier:
        def __init__(self):
            self.report = {"dataset": {"text_format": "compact-v5"}}

        def predict(self, text):
            inputs.append(text)
            return "T13"

    body = request_body()
    body["person_a"] = {
        "gender": "female", "birth_date": "1985-05-22", "birth_time": "23:38", "mbti": "INFP"
    }
    body["person_b"] = {
        "gender": "male", "birth_date": "1987-07-10", "birth_time": "14:20", "mbti": "ESTJ"
    }
    parsed = AnalysisInput.model_validate(body)
    assert to_saju_person(parsed.person_a)["saju"]["day"] == "壬戌"

    expected = analysis_inputs(parsed.person_a, parsed.person_b)
    assert expected["narrative"] == pair_text(parsed.person_a, parsed.person_b)[0]
    service = AnalysisService(mock_provider(calls=calls), RecordingClassifier())
    with TestClient(create_app(service)) as c:
        r = c.post("/api/v1/analyses", json=body)
        assert r.status_code == 200, r.text
        assert r.json()["result"]["limitations"] == expected["limitations"]
    assert inputs == [expected["compact"]]
    [call] = calls
    prompt = call["input"][1]["content"]
    assert expected["narrative"] in prompt
    assert "day_pillar" not in prompt and "unknown" not in prompt


@pytest.mark.parametrize("status", [401, 429, 500])
def test_provider_failure_no_save_ticket(live_config, status):
    calls = []

    def fail(r):
        calls.append(r)
        return httpx.Response(status, text="secret details must not leak")

    with TestClient(
        create_app(AnalysisService(OpenAIProvider(httpx.MockTransport(fail))))
    ) as c:
        r = c.post("/api/v1/analyses", json=request_body())
        assert r.status_code == 502
        assert "save_ticket" not in r.text and "secret" not in r.text
        assert len(calls) == 1


def test_daily_budget_and_deployment_origin(live_config, monkeypatch):
    monkeypatch.setattr(settings(), "daily_analysis_limit", 1)
    monkeypatch.setattr(settings(), "allowed_origins", "https://lovecode.example")
    with TestClient(create_app(AnalysisService(mock_provider()))) as c:
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
