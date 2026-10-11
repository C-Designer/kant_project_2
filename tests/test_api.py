import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from lovecode.db import audit, results
from lovecode.security import digest, verify
from sqlalchemy import func, select, update


def ticket(client):
    r = client.post("/api/v1/demo-analysis", json={})
    assert r.status_code == 200
    return r.json()["save_ticket"]


def body(client):
    return {
        "save_ticket": ticket(client),
        "read_token": secrets.token_urlsafe(32),
        "delete_token": secrets.token_urlsafe(32),
    }


def auth(token):
    return {"Authorization": "Bearer " + token}


def test_save_read_permissions_delete_replay(client, engine):
    b = body(client)
    with engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(results)) == 0
    save = client.post("/api/v1/results", json=b)
    assert save.status_code == 201
    id = save.json()["result_id"]
    again = client.post("/api/v1/results", json=b)
    assert again.status_code == 200
    assert again.json() == save.json()
    got = client.get("/api/v1/results", headers=auth(b["read_token"]))
    assert got.status_code == 200
    assert got.json()["result"]["evidence_status"] == "fixture"
    assert got.headers["cache-control"] == "no-store"
    assert "delete_token" not in got.text and "versions" not in got.text
    assert client.get("/api/v1/results", headers=auth(b["delete_token"])).status_code == 404
    assert client.delete("/api/v1/results/" + id, headers=auth(b["read_token"])).status_code == 404
    assert (
        client.post(
            "/api/v1/results", json={**b, "read_token": secrets.token_urlsafe(32)}
        ).status_code
        == 409
    )
    with engine.connect() as c:
        row = c.execute(select(results)).mappings().one()
        assert row["read_token_hash"] == digest(b["read_token"])
        assert row["delete_token_hash"] == digest(b["delete_token"])
        assert (row["expires_at"] - row["created_at"]) == timedelta(days=7)
    assert (
        client.delete("/api/v1/results/" + id, headers=auth(b["delete_token"])).status_code == 204
    )
    assert (
        client.delete("/api/v1/results/" + id, headers=auth(b["delete_token"])).status_code == 204
    )
    assert client.get("/api/v1/results", headers=auth(b["read_token"])).status_code == 404
    assert client.post("/api/v1/results", json=b).status_code == 410
    with engine.connect() as c:
        row = c.execute(select(results)).mappings().one()
        assert row["state"] == "revoked"
        assert all(
            row[k] is None
            for k in ["read_token_hash", "delete_token_hash", "result_payload", "versions"]
        )
        assert set(c.scalars(select(audit.c.action))) == {"result_saved", "result_revoked"}


def test_concurrent_save_same_keys(client, engine):
    b = body(client)
    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(pool.map(lambda _: client.post("/api/v1/results", json=b), range(5)))
    assert sorted(r.status_code for r in responses) == [200, 200, 200, 200, 201]
    assert len({r.json()["result_id"] for r in responses}) == 1
    with engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(results)) == 1
        assert c.scalar(select(func.count()).select_from(audit)) == 1


def test_concurrent_delete_retry_never_resurrects(client, engine):
    b = body(client)
    id = client.post("/api/v1/results", json=b).json()["result_id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        save = pool.submit(lambda: client.post("/api/v1/results", json=b))
        remove = pool.submit(
            lambda: client.delete("/api/v1/results/" + id, headers=auth(b["delete_token"]))
        )
        assert save.result().status_code in (200, 410)
        assert remove.result().status_code == 204
    assert client.get("/api/v1/results", headers=auth(b["read_token"])).status_code == 404
    assert client.post("/api/v1/results", json=b).status_code == 410


def test_expiry_guard_cleanup_and_tombstone(client, engine):
    b = body(client)
    client.post("/api/v1/results", json=b)
    with engine.begin() as c:
        c.execute(update(results).values(expires_at=func.clock_timestamp()))
    assert client.get("/api/v1/results", headers=auth(b["read_token"])).status_code == 404
    client.app.state.store.cleanup()
    with engine.connect() as c:
        row = c.execute(select(results)).mappings().one()
        assert row["result_payload"] is None
    with engine.begin() as c:
        c.execute(update(results).values(ticket_expires_at=func.clock_timestamp()))
    client.app.state.store.cleanup()
    with engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(results)) == 0


def test_invalid_requests_do_not_echo_or_persist(client, engine, caplog):
    canary = "PRIVATE_CANARY_BIRTH_1998_05_21"
    p = {"gender": "unspecified", "birth_date": "1998-05-21", "birth_time": None, "mbti": "INTP"}
    good = client.post("/api/v1/analyses", json={"person_a": p, "person_b": p})
    assert good.status_code == 503
    bad = client.post("/api/v1/analyses", json={"person_a": {**p, "mbti": canary}, "person_b": p})
    assert bad.status_code == 422
    assert canary not in bad.text and canary not in caplog.text
    assert client.post("/api/v1/demo-analysis", json={"name": canary}).status_code == 422
    with engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(results)) == 0
    assert (
        client.post(
            "/api/v1/analyses", content="x" * 42000, headers={"Content-Type": "application/json"}
        ).status_code
        == 413
    )
    assert (
        client.post(
            "/api/v1/demo-analysis", json={}, headers={"Origin": "https://example.com"}
        ).status_code
        == 403
    )


def test_ticket_tampering_invalid_keys_expiry(client, monkeypatch):
    b = body(client)
    assert (
        client.post(
            "/api/v1/results", json={**b, "save_ticket": b["save_ticket"] + "a"}
        ).status_code
        == 400
    )
    assert (
        client.post("/api/v1/results", json={**b, "delete_token": b["read_token"]}).status_code
        == 422
    )
    # Use this ticket's boundary, not module import time (which depends on suite speed).
    expires_at = verify(b["save_ticket"])["expires_at"]
    monkeypatch.setattr("lovecode.security.time.time", lambda: expires_at)
    assert client.post("/api/v1/results", json=b).status_code == 410
    assert client.get("/api/v1/results").status_code == 404
    assert (
        client.delete(
            "/api/v1/results/" + str(uuid.uuid4()), headers=auth(secrets.token_urlsafe(32))
        ).status_code
        == 204
    )


def test_rate_limit(client):
    from lovecode.settings import settings

    settings().rate_limit_enabled = True
    for _ in range(5):
        assert client.post("/api/v1/demo-analysis", json={}).status_code == 200
    r = client.post("/api/v1/demo-analysis", json={})
    assert r.status_code == 429
    assert "retry-after" in r.headers
    settings().rate_limit_enabled = False


def test_read_token_collision_is_conflict(client):
    first = body(client)
    assert client.post("/api/v1/results", json=first).status_code == 201
    second = body(client)
    second["read_token"] = first["read_token"]
    assert client.post("/api/v1/results", json=second).status_code == 409
    assert client.get("/api/v1/results", headers=auth(first["read_token"])).status_code == 200


def test_early_error_headers(client):
    r = client.post("/api/v1/demo-analysis", content="not JSON")
    assert r.status_code == 415
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["referrer-policy"] == "no-referrer"
