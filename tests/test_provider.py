import json

import httpx
import pytest
from lovecode.provider import LABEL_SCHEMA, OpenAIProvider, ProviderError
from lovecode.settings import settings


@pytest.fixture
def enabled():
    s = settings()
    old = {k: getattr(s, k) for k in ["api_enabled", "provider", "api_key", "model"]}
    s.api_enabled = True
    s.provider = "openai"
    s.api_key = "fixture-secret"
    s.model = "fixture-model"
    yield
    for k, v in old.items():
        setattr(s, k, v)


def test_disabled_no_network():
    called = []
    p = OpenAIProvider(httpx.MockTransport(lambda r: called.append(r)))
    with pytest.raises(ProviderError):
        p.label("가상", allow_paid=False)
    assert called == []


def test_responses_contract(enabled):
    def handler(r):
        body = json.loads(r.content)
        assert str(r.url) == "https://api.openai.com/v1/responses"
        assert body["store"] is False and body["text"]["format"]["strict"] is True
        assert body["model"] == "fixture-model"
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
                                    {"type_id": "T01", "label_reason": "fixture 근거"}
                                ),
                            }
                        ],
                    }
                ],
                "usage": {"total_tokens": 50},
            },
        )

    p = OpenAIProvider(httpx.MockTransport(handler))
    data, usage = p.label("가상", allow_paid=True)
    assert data["type_id"] == "T01" and usage["total_tokens"] == 50
    with pytest.raises(ProviderError):
        p.structured("actual", LABEL_SCHEMA, synthetic=False, allow_paid=True)


@pytest.mark.parametrize(
    "response",
    [
        {"status": "incomplete"},
        {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]},
        {"status": "completed", "output": []},
        {
            "status": "completed",
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "invalid json"}]}
            ],
        },
    ],
)
def test_failure_no_fake_result(enabled, response):
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(200, json=response)

    with pytest.raises(ProviderError):
        OpenAIProvider(httpx.MockTransport(handler)).label("가상", allow_paid=True)
    assert len(calls) == 1


def test_error_sanitized(enabled):
    p = OpenAIProvider(
        httpx.MockTransport(lambda r: httpx.Response(401, text="fixture-secret request content"))
    )
    with pytest.raises(ProviderError) as e:
        p.label("가상", allow_paid=True)
    assert str(e.value) == "PROVIDER_REQUEST_FAILED"


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"type_id": [], "label_reason": "요약"},
        {"type_id": "T01", "label_reason": 7},
        {"type_id": "T01", "label_reason": "=bad_formula"},
    ],
)
def test_malformed_label_rejected(enabled, data):
    response = {
        "status": "completed",
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(data)}]}
        ],
    }
    p = OpenAIProvider(httpx.MockTransport(lambda r: httpx.Response(200, json=response)))
    with pytest.raises(ProviderError, match="OUTPUT_REJECTED"):
        p.label("가상", allow_paid=True)
