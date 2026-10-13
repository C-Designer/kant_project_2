"""The deployed app must work without DB credentials and expose no persistence routes."""
from fastapi.testclient import TestClient
from lovecode.api import create_app
from lovecode.service import AnalysisService
from lovecode.settings import settings
from test_analysis import mock_provider, request_body


def test_stateless_real_analysis_without_database(monkeypatch):
    for key, value in {
        "share_save_enabled": False, "database_url": "", "signing_key": "",
        "api_enabled": True, "real_analysis_enabled": True, "provider": "openai",
        "api_key": "test-only", "model": "mock", "classifier_mode": "openai",
        "rate_limit_enabled": False,
    }.items():
        monkeypatch.setattr(settings(), key, value)

    def forbidden(*args, **kwargs):
        raise AssertionError("Stateless deployments must not connect to a DB or issue save tickets")

    monkeypatch.setattr("lovecode.api.make_engine", forbidden)
    monkeypatch.setattr("lovecode.api.issue", forbidden)
    with TestClient(create_app(analysis_service=AnalysisService(mock_provider("T13")))) as client:
        assert client.get("/api/v1/health").json()["analysis_ready"]
        result = client.post("/api/v1/analyses", json=request_body())
        assert result.status_code == 200
        assert result.json()["result"]["type_id"] == "T13"
        assert set(result.json()) == {"analysis_id", "result"}
        assert set(client.post("/api/v1/demo-analysis", json={}).json()) == {"analysis_id", "result"}
        assert client.post("/api/v1/results", json={}).status_code == 404
        assert client.get("/api/v1/results").status_code == 404
        assert client.delete("/api/v1/results/00000000-0000-0000-0000-000000000000").status_code == 404
