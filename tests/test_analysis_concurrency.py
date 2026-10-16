"""Exercise stage isolation, bounded admission and failure recovery without paid calls."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import anyio.to_thread
import pytest
from fastapi.testclient import TestClient
from lovecode.api import THREAD_HEADROOM, create_app
from lovecode.concurrency import AnalysisBusy, StageLimit
from lovecode.contracts import demo_result
from lovecode.service import AnalysisService
from lovecode.settings import settings
from test_analysis import request_body


def configure(monkeypatch):
    for name, value in {
        "rate_limit_enabled": False,
        "daily_analysis_limit": 40,
        "analysis_wait_seconds": 3,
        "classifier_mode": "local",
    }.items():
        monkeypatch.setattr(settings(), name, value)


class Classifier:
    def __init__(self, expected=20):
        self.expected = expected
        self.report = {"dataset": {"text_format": "compact-v5"}}
        self.lock = threading.Lock()
        self.active = self.peak = self.calls = 0
        self.all_called = threading.Event()

    def predict(self, text):
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        time.sleep(0.01)
        with self.lock:
            self.active -= 1
            self.calls += 1
            if self.calls == self.expected:
                self.all_called.set()
        return "T13"


class Explainer:
    def __init__(self):
        self.release = threading.Event()
        self.lock = threading.Lock()
        self.active = self.peak = 0

    def explain(self, *args, **kwargs):
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            assert self.release.wait(5)
            return demo_result(), {}
        finally:
            with self.lock:
                self.active -= 1


def test_twenty_requests_release_bert_before_explanation_and_reject_overflow(monkeypatch):
    configure(monkeypatch)
    # Pinned below the defaults so explanation slots, not admission, are the bottleneck.
    monkeypatch.setattr(settings(), "analysis_capacity", 20)
    monkeypatch.setattr(settings(), "explanation_concurrency", 5)
    classifier, explainer = Classifier(), Explainer()
    service = AnalysisService(classifier=classifier, explainer=explainer)
    monkeypatch.setattr(service, "ready", lambda: True)
    with TestClient(create_app(analysis_service=service)) as client, ThreadPoolExecutor(20) as pool:
        futures = [
            pool.submit(client.post, "/api/v1/analyses", json=request_body()) for _ in range(20)
        ]
        try:
            # All 20 classifications finish even while every explanation is held.
            assert classifier.all_called.wait(3)
            response = client.post("/api/v1/analyses", json=request_body())
            assert response.status_code == 429
            assert response.json()["error"]["code"] == "ANALYSIS_BUSY"
            assert response.headers["Retry-After"] == "5"
            assert classifier.peak == 2
            assert explainer.peak == 5
        finally:
            explainer.release.set()
        assert [f.result().status_code for f in futures] == [200] * 20
        assert client.post("/api/v1/analyses", json=request_body()).status_code == 200


def test_default_fifty_requests_wait_on_openai_together_and_reject_overflow(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(settings(), "daily_analysis_limit", 100)
    assert settings().analysis_capacity == settings().explanation_concurrency == 50
    assert settings().bert_concurrency == 2
    classifier, explainer = Classifier(expected=50), Explainer()
    service = AnalysisService(classifier=classifier, explainer=explainer)
    monkeypatch.setattr(service, "ready", lambda: True)
    with TestClient(create_app(analysis_service=service)) as client, ThreadPoolExecutor(50) as pool:
        futures = [
            pool.submit(client.post, "/api/v1/analyses", json=request_body()) for _ in range(50)
        ]
        try:
            # Needs 50 worker threads at once: anyio's default 40 would leave 10 queued.
            assert classifier.all_called.wait(5)
            deadline = time.monotonic() + 3
            while explainer.active < 50 and time.monotonic() < deadline:
                time.sleep(0.005)
            assert explainer.active == 50
            response = client.post("/api/v1/analyses", json=request_body())
            assert response.status_code == 429
            assert response.json()["error"]["code"] == "ANALYSIS_BUSY"
            # Spare threads keep cheap endpoints answering while every slot is held.
            assert client.get("/api/v1/health").status_code == 200
            assert classifier.peak == 2
            assert explainer.peak == 50
        finally:
            explainer.release.set()
        assert [f.result().status_code for f in futures] == [200] * 50


def thread_tokens(client):
    return client.portal.call(lambda: anyio.to_thread.current_default_thread_limiter().total_tokens)


def test_lifespan_sizes_thread_pool_above_admission(monkeypatch):
    with TestClient(create_app()) as client:
        assert thread_tokens(client) == settings().analysis_capacity + THREAD_HEADROOM == 60
    monkeypatch.setattr(settings(), "analysis_capacity", 4)
    with TestClient(create_app()) as client:
        # Never shrinks below anyio's own default of 40.
        assert thread_tokens(client) == 40


def test_concurrency_bounds_accept_fifty_and_reject_beyond_ceiling():
    from lovecode.settings import Settings
    from pydantic import ValidationError

    ok = Settings(analysis_capacity=50, explanation_concurrency=50, _env_file=None)
    assert (ok.analysis_capacity, ok.explanation_concurrency) == (50, 50)
    for field in ("analysis_capacity", "explanation_concurrency"):
        with pytest.raises(ValidationError):
            Settings(**{field: 65}, _env_file=None)
    with pytest.raises(ValidationError):
        Settings(bert_concurrency=3, _env_file=None)


def test_fifo_timeout_and_exception_release():
    stage = StageLimit(1)
    order = []

    def worker(number, duration):
        with stage.acquire(time.monotonic() + duration):
            order.append(number)

    with ThreadPoolExecutor(3) as pool:
        with stage.acquire(time.monotonic() + 1):
            timeout = pool.submit(worker, 0, 0.02)
            with pytest.raises(AnalysisBusy):
                timeout.result()
            a = pool.submit(worker, 1, 2)
            while len(stage.waiters) < 1:
                time.sleep(0.001)
            b = pool.submit(worker, 2, 2)
            while len(stage.waiters) < 2:
                time.sleep(0.001)
        a.result()
        b.result()
    assert order == [1, 2]
    with pytest.raises(RuntimeError), stage.acquire(time.monotonic() + 1):
        raise RuntimeError("failed inference")
    with stage.acquire(time.monotonic() + 1):
        assert stage.active == 1
    assert stage.active == 0
    assert not stage.waiters


def test_stage_timeout_returns_retryable_busy_and_frees_admission(monkeypatch):
    configure(monkeypatch)
    service = AnalysisService(classifier=Classifier(), explainer=Explainer())
    monkeypatch.setattr(service, "ready", lambda: True)
    monkeypatch.setattr(settings(), "analysis_capacity", 1)
    monkeypatch.setattr(settings(), "analysis_wait_seconds", 0.01)
    with TestClient(create_app(analysis_service=service)) as client:
        with (
            service._bert_slots.acquire(time.monotonic() + 1),
            service._bert_slots.acquire(time.monotonic() + 1),
        ):
            for _ in range(2):
                r = client.post("/api/v1/analyses", json=request_body())
                assert r.status_code == 429
                assert r.json()["error"]["code"] == "ANALYSIS_BUSY"
        service.explainer.release.set()
        assert client.post("/api/v1/analyses", json=request_body()).status_code == 200


def test_explanation_failure_releases_both_stage_and_admission(monkeypatch):
    from lovecode.provider import ProviderError

    configure(monkeypatch)
    monkeypatch.setattr(settings(), "analysis_capacity", 1)
    monkeypatch.setattr(settings(), "explanation_concurrency", 1)
    explainer = Explainer()
    calls = []

    def explain(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise ProviderError("upstream unavailable")
        return demo_result(), {}

    monkeypatch.setattr(explainer, "explain", explain)
    service = AnalysisService(classifier=Classifier(), explainer=explainer)
    monkeypatch.setattr(service, "ready", lambda: True)
    with TestClient(create_app(analysis_service=service)) as client:
        assert client.post("/api/v1/analyses", json=request_body()).status_code == 502
        assert client.post("/api/v1/analyses", json=request_body()).status_code == 200
    assert service._bert_slots.active == service._explanation_slots.active == 0
