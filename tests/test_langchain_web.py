"""Exercise the web explainer through the real LangChain/OpenAI SDK, with offline HTTP."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from langsmith import get_tracing_context
from lovecode.api import create_app
from lovecode.contracts import TAXONOMY, demo_result
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
        assert body["store"] is False and body["max_output_tokens"] == 3500
        assert body["text"]["format"]["strict"] is True
        assert "type_id" not in body["text"]["format"]["schema"]["properties"]
        assert "1994-06-15" not in request.content.decode()
        if status in (429, 500):
            return httpx.Response(status, json={"error": {"message": "private error"}})
        result = demo_result().model_dump(
            include={"summary", "strengths", "adjustments", "conversation_tip"}
        )
        if "spicy" in body["text"]["format"]["schema"]["properties"]:
            result["spicy"] = demo_result().spicy.notes
        if "reading" in body["text"]["format"]["schema"]["properties"]:
            # The prompt hands over the rule signals and the A/B names (T13 poles only).
            prompt = body["input"][1]["content"]
            assert "축별 근거" in prompt and "첫 번째 분" in prompt
            result["reading"] = {
                "first_person": "차분하게 계획을 세우는 분이에요.",
                "second_person": "마음을 먼저 표현하는 분이에요.",
                "chemistry": "서로 없는 기운을 채워 주는 보완형이에요.",
                "temperature": "꾸준한 온기가 어울리는 안정형이에요.",
                "distance": "함께하는 시간이 늘어나는 밀착형이에요.",
                "conflict": "그 자리에서 대화로 푸는 바로 풀기가 맞아요.",
            }
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
                spicy = response.json()["result"]["spicy"]
                assert set(spicy["titles"]) == {"skinship", "temptation", "jealousy", "reunion"}
                assert response.json()["result"]["schema_version"] == "1.2"
                reading = response.json()["result"]["reading"]
                assert set(reading["axes"]) == {"chemistry", "temperature", "distance", "conflict"}
                assert len(reading["people"]) == 2
            else:
                assert response.status_code == 502
                assert "save_ticket" not in response.text


def test_default_service_uses_langchain():
    assert isinstance(AnalysisService().explainer, LangChainExplainer)


@pytest.mark.parametrize("type_id", list(TAXONOMY))
def test_prompt_shows_only_own_poles(type_id):
    # The opposite_pole check rejects these words, so the prompt itself must not show them.
    from lovecode.checks import opposite_poles, poles
    from lovecode.generator import prompt, prompt_inputs, repair_prompt

    inputs = prompt_inputs("", type_id)
    rendered = [
        "\n".join(m.content for m in prompt().format_messages(**inputs)),
        "\n".join(
            m.content
            for m in repair_prompt().format_messages(**inputs, previous="{}", problems="")
        ),
    ]
    for text in rendered:
        assert all(pole in text for pole in poles(type_id))
        assert not [pole for pole in opposite_poles(type_id) if pole in text]
        # The first draft is told the rule the opposite_pole check enforces, not only the repair.
        assert "반대쪽 극의 이름은 비교하거나 대조할 때도 쓰지 않는다" in text
