import asyncio
import logging
import re
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .concurrency import AnalysisBusy
from .contracts import (
    TAXONOMY,
    AnalysisInput,
    AnalysisResponse,
    SavedResponse,
    SaveInput,
    SharedResponse,
    Strict,
    demo_result,
)
from .db import Store, StoreError, make_engine, metadata
from .provider import ProviderError
from .security import TicketError, issue, verify
from .service import AnalysisService
from .settings import settings

log = logging.getLogger("lovecode")


def error(code, status, message="요청을 처리하지 못했어요. 다시 확인해 주세요.", field=None):
    return JSONResponse(
        {
            "error": {"code": code, "message": message, "field": field, "retryable": status >= 500},
            "request_id": str(uuid.uuid4()),
        },
        status_code=status,
    )


def create_app(engine=None, analysis_service=None):
    storage_enabled = settings().share_save_enabled
    engine = (engine or make_engine(settings().database_url)) if storage_enabled else None
    store = Store(engine) if storage_enabled else None
    service = analysis_service or AnalysisService()
    # Bound total in-flight work; the service independently limits each expensive stage.
    analysis_admission = threading.BoundedSemaphore(settings().analysis_capacity)
    budget_lock = threading.Lock()
    budget = {"day": "", "count": 0}

    @asynccontextmanager
    async def lifespan(app):
        if not storage_enabled:
            yield
            return
        metadata.create_all(engine)

        async def cleanup():
            while True:
                try:
                    await asyncio.to_thread(store.cleanup)
                except SQLAlchemyError:
                    log.error("expiry_cleanup_failed")
                await asyncio.sleep(60)

        worker = asyncio.create_task(cleanup())
        yield
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass

    app = FastAPI(
        title="러브코드 로컬 MVP",
        version="0.2.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/docs",
        lifespan=lifespan,
    )
    app.state.store = store
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
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

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

    @app.exception_handler(StoreError)
    async def store_error(request, exc):
        return error(exc.code, exc.status)

    @app.exception_handler(SQLAlchemyError)
    async def storage_error(request, exc):
        log.error("storage_unavailable")
        return error(
            "STORAGE_UNAVAILABLE", 503, "저장소에 연결하지 못했어요. 잠시 후 다시 시도해 주세요."
        )

    def bearer(request):
        token = request.headers.get("authorization", "")
        if not re.fullmatch(r"Bearer [A-Za-z0-9_-]{43}", token):
            raise StoreError("RESULT_UNAVAILABLE", 404)
        return token[7:]

    @app.get("/api/v1/health")
    def health():
        if engine is not None:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "analysis_ready": service.ready(),
            "demo_ready": settings().demo_enabled,
            "provider": "openai",
            "verification_mode": service.provider.transport is not None,
            "reason": "configured_not_quality_certified"
            if service.ready()
            else "configuration_required",
        }

    @app.get("/api/v1/taxonomy")
    def taxonomy():
        return TAXONOMY

    def analysis_response(result, versions=None):
        if not storage_enabled:
            return {"analysis_id": str(uuid.uuid4()), "result": result.model_dump()}
        p, ticket = issue(result, versions)
        return {
            "analysis_id": p["analysis_id"],
            "result": p["result"],
            "save_ticket": ticket,
            "save_expires_at": datetime.fromtimestamp(p["expires_at"], UTC),
        }

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
            result, versions = service.analyse(body)
            return analysis_response(result, versions)
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

    # Stateless deployments expose no save, share-read, or delete routes.
    if not storage_enabled:
        return app

    @app.post("/api/v1/results", response_model=SavedResponse)
    def save(body: SaveInput, response: Response):
        if not settings().share_save_enabled:
            return error("STORAGE_UNAVAILABLE", 503)
        try:
            p = verify(body.save_ticket)
        except TicketError as e:
            return error(
                "SAVE_TICKET_EXPIRED" if e.expired else "INVALID_SAVE_TICKET",
                410 if e.expired else 400,
            )
        result, new = store.save(p, body.read_token, body.delete_token)
        response.status_code = 201 if new else 200
        return result

    @app.get("/api/v1/results", response_model=SharedResponse)
    def get(request: Request):
        return store.get(bearer(request))

    @app.delete("/api/v1/results/{result_id}", status_code=204)
    def remove(result_id: uuid.UUID, request: Request):
        store.remove(str(result_id), bearer(request))
        return Response(status_code=204)

    return app


app = create_app()
