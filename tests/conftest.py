import os

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from lovecode.api import create_app
from lovecode.db import make_engine, metadata
from lovecode.settings import settings
from sqlalchemy import text


@pytest.fixture(scope="session")
def engine():
    url = os.environ.get("LC_TEST_DATABASE_URL") or dotenv_values(".env")["LC_TEST_DATABASE_URL"]
    if not url.endswith("/lovecode_test"):
        raise RuntimeError("Tests only operate on isolated lovecode_test database")
    e = make_engine(url)
    metadata.create_all(e)
    yield e
    e.dispose()


@pytest.fixture
def client(engine):
    with engine.begin() as c:
        c.execute(text("TRUNCATE shared_results, audit_events"))
    original = settings().rate_limit_enabled
    settings().rate_limit_enabled = False
    with TestClient(create_app(engine)) as c:
        yield c
    settings().rate_limit_enabled = original


@pytest.fixture(autouse=True)
def offline_api_boundary(monkeypatch):
    """A future real .env key must never turn this test suite into paid traffic."""
    import httpx

    monkeypatch.setattr(settings(), "api_enabled", False)
    monkeypatch.setattr(settings(), "real_analysis_enabled", False)

    def reject_network(*args, **kwargs):
        raise AssertionError("Real HTTP requests are forbidden in offline tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", reject_network)
