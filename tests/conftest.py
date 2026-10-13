import pytest
from fastapi.testclient import TestClient
from lovecode.api import create_app
from lovecode.settings import settings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings(), "rate_limit_enabled", False)
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture(autouse=True)
def offline_api_boundary(monkeypatch):
    """A future real .env key must never turn this test suite into paid traffic."""
    import httpx

    monkeypatch.setattr(settings(), "api_enabled", False)
    monkeypatch.setattr(settings(), "real_analysis_enabled", False)

    def reject_network(*args, **kwargs):
        raise AssertionError("Real HTTP requests are forbidden in offline tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", reject_network)
