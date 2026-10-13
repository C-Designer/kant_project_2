"""Bounded waiting uses real API threads; fake analysis makes no paid network calls."""
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from fastapi.testclient import TestClient
from lovecode.api import create_app
from lovecode.contracts import demo_result
from lovecode.settings import settings
from test_analysis import request_body


class HeldAnalysis:
    def __init__(self):
        self.release = threading.Event()
        self.two_running = threading.Event()
        self.lock = threading.Lock()
        self.running = 0
        self.peak = 0
        self.calls = 0

    def ready(self):
        return True

    def analyse(self, body):
        with self.lock:
            self.calls += 1
            self.running += 1
            self.peak = max(self.peak, self.running)
            if self.running == 2:
                self.two_running.set()
        try:
            assert self.release.wait(5), "Test did not release analysis"
            return demo_result(), {}
        finally:
            with self.lock:
                self.running -= 1


def configure(monkeypatch, wait_seconds):
    monkeypatch.setattr(settings(), "share_save_enabled", False)
    monkeypatch.setattr(settings(), "rate_limit_enabled", False)
    monkeypatch.setattr(settings(), "analysis_wait_seconds", wait_seconds)
    monkeypatch.setattr(settings(), "daily_analysis_limit", 20)


def test_two_running_four_waiting_and_overflow(monkeypatch):
    configure(monkeypatch, 3)
    service = HeldAnalysis()
    with TestClient(create_app(analysis_service=service)) as client, ThreadPoolExecutor(7) as pool:
        futures = [pool.submit(client.post, "/api/v1/analyses", json=request_body()) for _ in range(7)]
        try:
            assert service.two_running.wait(2)
            done, _ = wait(futures, timeout=2, return_when=FIRST_COMPLETED)
            assert len(done) == 1
            rejected = next(iter(done)).result()
            assert rejected.status_code == 429
            assert rejected.json()["error"]["code"] == "ANALYSIS_BUSY"
            assert rejected.headers["Retry-After"] == "5"
            assert service.calls == 2  # Waiting requests have not started expensive work.
        finally:
            service.release.set()
        assert sorted(f.result().status_code for f in futures) == [200] * 6 + [429]
        assert service.peak == 2
        assert client.post("/api/v1/analyses", json=request_body()).status_code == 200


def test_wait_timeout_releases_admission_and_does_not_call_model(monkeypatch):
    configure(monkeypatch, 0.02)
    service = HeldAnalysis()
    with TestClient(create_app(analysis_service=service)) as client, ThreadPoolExecutor(2) as pool:
        active = [pool.submit(client.post, "/api/v1/analyses", json=request_body()) for _ in range(2)]
        try:
            assert service.two_running.wait(2)
            for _ in range(5):
                response = client.post("/api/v1/analyses", json=request_body())
                assert response.status_code == 429
                assert response.headers["Retry-After"] == "5"
            assert service.calls == 2
        finally:
            service.release.set()
        assert all(f.result().status_code == 200 for f in active)
        assert client.post("/api/v1/analyses", json=request_body()).status_code == 200
