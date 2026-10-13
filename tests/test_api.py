def test_invalid_requests_do_not_echo_or_persist(client, caplog):
    canary = "PRIVATE_CANARY_BIRTH_1998_05_21"
    p = {"gender": "unspecified", "birth_date": "1998-05-21", "birth_time": None, "mbti": "INTP"}
    good = client.post("/api/v1/analyses", json={"person_a": p, "person_b": p})
    assert good.status_code == 503
    bad = client.post("/api/v1/analyses", json={"person_a": {**p, "mbti": canary}, "person_b": p})
    assert bad.status_code == 422
    assert canary not in bad.text and canary not in caplog.text
    assert client.post("/api/v1/demo-analysis", json={"name": canary}).status_code == 422
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


def test_rate_limit(client):
    from lovecode.settings import settings

    settings().rate_limit_enabled = True
    for _ in range(5):
        assert client.post("/api/v1/demo-analysis", json={}).status_code == 200
    r = client.post("/api/v1/demo-analysis", json={})
    assert r.status_code == 429
    assert "retry-after" in r.headers
    settings().rate_limit_enabled = False


def test_early_error_headers(client):
    r = client.post("/api/v1/demo-analysis", content="not JSON")
    assert r.status_code == 415
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["referrer-policy"] == "no-referrer"
