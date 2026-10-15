import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime

from fastapi import FastAPI, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .concurrency import AnalysisBusy
from .contracts import (
    TAXONOMY,
    AnalysisInput,
    AnalysisResponse,
    SharedResult,
    Strict,
    demo_result,
)
from .provider import ProviderError
from .service import AnalysisService
from .settings import settings
from .share import MAX_CODE_CHARS, ShareCodec, ShareError


def error(code, status, message="요청을 처리하지 못했어요. 다시 확인해 주세요.", field=None):
    return JSONResponse(
        {
            "error": {"code": code, "message": message, "field": field, "retryable": status >= 500},
            "request_id": str(uuid.uuid4()),
        },
        status_code=status,
    )


def create_app(analysis_service=None, share_codec=None):
    service = analysis_service or AnalysisService()
    shares = share_codec or ShareCodec.from_settings()
    # Bound total in-flight work; the service independently limits each expensive stage.
    analysis_admission = threading.BoundedSemaphore(settings().analysis_capacity)
    budget_lock = threading.Lock()
    budget = {"day": "", "count": 0}

    app = FastAPI(
        title="러브코드 로컬 MVP",
        version="0.2.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/docs",
    )
    buckets = defaultdict(deque)
    salt = secrets.token_bytes(32)
    salt_time = time.monotonic()

    @app.middleware("http")
    async def boundary(request, call_next):
        nonlocal salt, salt_time
        if request.method in ("POST", "DELETE") and request.headers.get("origin") not in (
            None,
            *settings().allowed_origins.split(","),
        ):
            return error("INVALID_REQUEST", 403)
        if request.method == "POST":
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return error("INVALID_REQUEST", 415)
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 40960:
                    return error("PAYLOAD_TOO_LARGE", 413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        if settings().rate_limit_enabled:
            import hashlib

            now = time.monotonic()
            if now - salt_time > 600:
                buckets.clear()
                salt = secrets.token_bytes(32)
                salt_time = now
            group = (
                "analysis"
                if request.url.path.endswith(("analyses", "demo-analysis"))
                else request.method
            )
            limit, window = {
                "analysis": (5, 600),
                "POST": (10, 600),
                "GET": (60, 60),
                "DELETE": (10, 60),
            }.get(group, (60, 60))
            key = (
                hashlib.sha256(
                    salt + (request.client.host if request.client else "unknown").encode()
                ).digest(),
                group,
            )
            q = buckets[key]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                r = error("RATE_LIMITED", 429, "잠시 후 다시 시도해 주세요.")
                r.headers["Retry-After"] = str(int(window))
                return r
            q.append(now)
        return await call_next(request)

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        loc = exc.errors()[0]["loc"]
        return error(
            "INVALID_REQUEST",
            422,
            "입력값을 다시 확인해 주세요.",
            ".".join(str(x) for x in loc if x != "body"),
        )

    @app.get("/api/v1/health")
    def health():
        ready = service.ready()
        return {
            "status": "ok",
            "analysis_ready": ready,
            "demo_ready": settings().demo_enabled,
            "provider": "openai",
            "verification_mode": service.provider.transport is not None,
            "share_ready": shares.ready,
            "reason": "configured_not_quality_certified"
            if ready
            else "configuration_required",
        }

    @app.get("/api/v1/taxonomy")
    def taxonomy():
        return TAXONOMY

    def analysis_response(result, shareable=False):
        body = {"analysis_id": str(uuid.uuid4()), "result": result.model_dump()}
        if shareable and shares.ready and (code := shares.encode(result)):
            body["share_code"] = code
        return body

    @app.post("/api/v1/analyses", response_model=AnalysisResponse, response_model_exclude_none=True)
    def analyse(body: AnalysisInput):
        if not service.ready():
            return error(
                "ANALYSIS_UNAVAILABLE",
                503,
                "실제 분석은 아직 준비 중이에요. 예시 결과를 둘러볼 수 있어요.",
            )
        if not body.external_processing_consent:
            return error("CONSENT_REQUIRED", 422, "OpenAI 처리 동의를 확인해 주세요.")
        def busy():
            response = error(
                "ANALYSIS_BUSY", 429,
                "분석 요청이 많아 대기 시간이 길어지고 있어요. 잠시 후 다시 시도해 주세요.",
            )
            response.headers["Retry-After"] = "5"
            return response

        if not analysis_admission.acquire(blocking=False):
            return busy()
        try:
            with budget_lock:
                day = datetime.now(UTC).date().isoformat()
                if budget["day"] != day:
                    budget.update(day=day, count=0)
                if budget["count"] >= settings().daily_analysis_limit:
                    return error(
                        "DAILY_LIMIT", 429, "오늘의 분석 한도에 도달했어요. 다음에 다시 찾아주세요."
                    )
                budget["count"] += 1
            result, _ = service.analyse(body)
            return analysis_response(result, shareable=True)
        except AnalysisBusy:
            return busy()
        except ProviderError:
            return error(
                "PROVIDER_UNAVAILABLE", 502, "분석을 마치지 못했어요. 잠시 후 다시 시도해 주세요."
            )
        except (ValueError, OSError, KeyError):
            return error(
                "ANALYSIS_UNAVAILABLE",
                503,
                "분석 설정을 확인하고 있어요. 잠시 후 다시 시도해 주세요.",
            )
        finally:
            analysis_admission.release()

    @app.post("/api/v1/demo-analysis", response_model=AnalysisResponse, response_model_exclude_none=True)
    def demo(body: Strict):
        if not settings().demo_enabled:
            return error("ANALYSIS_UNAVAILABLE", 503)
        return analysis_response(demo_result())

    # The code arrives in a header, not the URL, so access logs never hold shared results.
    @app.get(
        "/api/v1/shared",
        response_model=SharedResult,
        responses={
            400: {"description": "INVALID_SHARE_LINK: 변조·잘림·다른 키로 서명된 링크"},
            503: {"description": "SHARE_UNAVAILABLE: LC_SHARE_SECRET 미설정"},
        },
    )
    def shared(x_share_code: str = Header(default="", max_length=MAX_CODE_CHARS)):
        try:
            return shares.decode(x_share_code)
        except ShareError as e:
            return error(e.code, e.status, e.message)

    return app


app = create_app()
