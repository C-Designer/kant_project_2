"""Disposable browser rehearsal. Mock network only, no database, never a deploy entrypoint."""

import json
import os

import httpx
import uvicorn

# Override before importing settings/app. Never print credentials.
os.environ.update(
    LC_API_ENABLED="true",
    LC_REAL_ANALYSIS_ENABLED="true",
    LC_PROVIDER="openai",
    LC_API_KEY="mock-only-not-a-key",
    LC_MODEL="mock-only",
    LC_CLASSIFIER_MODE="openai",
    LC_DAILY_ANALYSIS_LIMIT="20",
)
from lovecode.api import create_app
from lovecode.contracts import demo_result
from lovecode.provider import OpenAIProvider
from lovecode.service import AnalysisService


def handle(request):
    body = json.loads(request.content)
    if "type_id" in body["text"]["format"]["schema"]["properties"]:
        data = {"type_id": "T14", "label_reason": "모의 응답: 배선 검증용"}
    else:
        data = demo_result().model_dump(
            include={"summary", "strengths", "adjustments", "conversation_tip"}
        )
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


if __name__ == "__main__":
    service = AnalysisService(OpenAIProvider(httpx.MockTransport(handle)))
    uvicorn.run(create_app(analysis_service=service), host="127.0.0.1", port=8100, access_log=False)
