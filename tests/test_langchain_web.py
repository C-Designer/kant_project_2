"""Exercise the web explainer through the real LangChain/OpenAI SDK, with offline HTTP."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from langsmith import get_tracing_context
from lovecode.api import create_app
from lovecode.contracts import demo_result
from lovecode.generator import LangChainExplainer, make_llm
from lovecode.service import AnalysisService
from lovecode.settings import settings


@pytest.mark.parametrize("status", [200, 429, 500, "incomplete", "refusal", "invalid"])
def test_langchain_web_transport(monkeypatch, status):
    for key, value in {
        "api_enabled": True, "real_analysis_enabled": True,
        "api_key": "test-only", "model": "configured-model", "provider": "openai",
        "classifier_mode": "local", "rate_limit_enabled": False,
    }.items():
        monkeypatch.setattr(settings(), key, value)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    calls = []

    def respond(request):
        assert get_tracing_context()["enabled"] is False
        body = json.loads(request.content)
        calls.append(body)
        assert request.url.path == "/v1/responses"
        assert body["store"] is False and body["max_output_tokens"] == 2000
        assert body["text"]["format"]["strict"] is True
        assert "type_id" not in body["text"]["format"]["schema"]["properties"]
        assert "1994-06-15" not in request.content.decode()
        if status in (429, 500):
            return httpx.Response(status, json={"error": {"message": "private error"}})
        result = demo_result().model_dump(
            include={"summary", "strengths", "adjustments", "conversation_tip"}
        )
        if status == "invalid":
            result["summary"] = "INTJ와 ENFP"
        content = [{"type": "output_text", "text": json.dumps(result), "annotations": []}]
        if status == "refusal":
            content = [{"type": "refusal", "refusal": "private refusal"}]
        return httpx.Response(200, json={
            "id": "resp_test", "object": "response", "created_at": 0,
            "model": "configured-model",
            "status": "incomplete" if status == "incomplete" else "completed",
            "output": [{"id": "msg_test", "type": "message", "role": "assistant",
                        "status": "completed", "content": content}],
        })

    class Classifier:
        def __init__(self):
            self.report = {"dataset": {"text_format": "compact-v5"}}

        def predict(self, text):
            return "T13"

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        llm = make_llm("openai", "configured-model", http_client=client)
        explainer = LangChainExplainer("openai", llm=llm)
        service = AnalysisService(classifier=Classifier(), explainer=explainer)
        with TestClient(create_app(service)) as web:
            body = {
                "external_processing_consent": False,
                "person_a": {"gender": "male", "birth_date": "1994-06-15",
                             "birth_time": None, "mbti": "INTJ"},
                "person_b": {"gender": "female", "birth_date": "1996-09-20",
                             "birth_time": "14:30", "mbti": "ENFP"},
            }
            assert web.post("/api/v1/analyses", json=body).status_code == 422
            assert not calls
            body["external_processing_consent"] = True
            response = web.post("/api/v1/analyses", json=body)
            # Bad outputs get one repair call; HTTP/provider errors are not retried.
            assert len(calls) == (1 if status in (200, 429, 500) else 2)
            assert "private error" not in response.text
            if status == 200:
                assert response.status_code == 200, response.text
                assert response.json()["result"]["type_id"] == "T13"
            else:
                assert response.status_code == 502
                assert "save_ticket" not in response.text


def test_default_service_uses_langchain():
    assert isinstance(AnalysisService().explainer, LangChainExplainer)
