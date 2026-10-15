"""Stateless share links: signed, compressed results; nothing is stored on the server."""

import base64
import hashlib
import hmac
import json
import random
import zlib

import pytest
from fastapi.testclient import TestClient
from lovecode.api import create_app
from lovecode.contracts import TAXONOMY, SpicyResult, SpicyTitle, demo_result
from lovecode.service import AnalysisService
from lovecode.settings import settings
from lovecode.share import MAX_CODE_CHARS, ShareCodec, ShareError
from lovecode.spicy import NOTE_MAX, TITLE_MAX, TOPICS
from test_analysis import mock_provider, request_body

SECRET = "s" * 40
NOW = 1_800_000_000


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def deflate(data):
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


def signed(body, secret=SECRET):
    mac = hmac.new(secret.encode(), b"lovecode-share.v1." + body, hashlib.sha256).digest()[:16]
    return b64(body) + "." + b64(mac)


def payload_code(payload, secret=SECRET):
    return signed(deflate(json.dumps(payload, ensure_ascii=False).encode()), secret)


def demo_fields(**changes):
    fields = demo_result().model_dump(
        mode="json", exclude={"axes", "schema_version", "taxonomy_version", "disclaimer_version"}
    )
    return {**fields, "evidence_status": "ai_draft_unreviewed", **changes}


@pytest.fixture
def client(monkeypatch):
    for key, value in {
        "api_enabled": True, "real_analysis_enabled": True, "provider": "openai",
        "api_key": "test-only", "model": "mock", "classifier_mode": "openai",
        "rate_limit_enabled": False,
    }.items():
        monkeypatch.setattr(settings(), key, value)
    app = create_app(
        analysis_service=AnalysisService(mock_provider("T13")),
        share_codec=ShareCodec(SECRET, clock=lambda: NOW),
    )
    with TestClient(app) as c:
        yield c


def open_link(client, code):
    return client.get("/api/v1/shared", headers={"X-Share-Code": code})


def test_round_trip_returns_the_same_result(client):
    assert client.get("/api/v1/health").json()["share_ready"] is True
    analysis = client.post("/api/v1/analyses", json=request_body()).json()
    code = analysis["share_code"]
    r = open_link(client, code)
    assert r.status_code == 200
    assert r.json()["result"] == analysis["result"]
    # NOW is 2027-01-15 17:00 KST; only the Korean calendar day is kept (midnight KST in UTC).
    assert r.json()["created_at"] == "2027-01-14T15:00:00Z"
    assert r.headers["cache-control"] == "no-store"


def test_link_carries_no_raw_inputs_and_stays_short(client):
    analysis = client.post("/api/v1/analyses", json=request_body()).json()
    body = analysis["share_code"].split(".")[0]
    text = zlib.decompress(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)), -15).decode()
    for raw_input in ("1994-06-15", "1996-09-20", "14:30", "INTJ", "ENFP", "female"):
        assert raw_input not in text
    assert len(analysis["share_code"]) < 2000  # 1.1 adds four spicy titles and notes


def random_hangul(n, rng):
    return "".join(chr(rng.randrange(0xAC00, 0xD7A4)) for _ in range(n))


def test_worst_case_result_fits_the_code_limit():
    """Random syllables barely compress, so this is close to the real upper bound."""
    rng = random.Random(7)
    result = demo_result().model_copy(
        update={
            "summary": random_hangul(120, rng),
            "strengths": [random_hangul(180, rng), random_hangul(180, rng)],
            "adjustments": [random_hangul(180, rng), random_hangul(180, rng)],
            "conversation_tip": random_hangul(180, rng),
            "limitations": ["missing_hour_a", "missing_hour_b", "boundary_time_unknown_a",
                            "boundary_time_unknown_b"],
            "spicy": SpicyResult(
                titles={t: SpicyTitle(id=i, text=random_hangul(TITLE_MAX, rng))
                        for t, i in zip(TOPICS, ("S1", "C1", "J1", "R1"))},
                notes={t: random_hangul(NOTE_MAX, rng) for t in TOPICS},
            ),
        }
    )
    codec = ShareCodec(SECRET)
    code = codec.encode(result)
    assert code is not None and len(code) <= MAX_CODE_CHARS
    assert codec.decode(code).result == result


def test_a_code_that_would_not_fit_is_left_out(client, monkeypatch):
    import lovecode.share

    monkeypatch.setattr(lovecode.share, "MAX_CODE_CHARS", 100)
    analysis = client.post("/api/v1/analyses", json=request_body()).json()
    assert "share_code" not in analysis
    assert analysis["result"]["type_id"] == "T13"


def test_each_link_has_exactly_one_spelling(client):
    code = client.post("/api/v1/analyses", json=request_body()).json()["share_code"]
    body, sig = code.split(".")
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    twin = alphabet[alphabet.index(sig[-1]) ^ 1]  # same decoded bytes, different text
    assert base64.urlsafe_b64decode(sig[:-1] + twin + "==") == base64.urlsafe_b64decode(sig + "==")
    r = open_link(client, body + "." + sig[:-1] + twin)
    assert r.status_code == 400


def test_any_tampering_is_refused(client):
    code = client.post("/api/v1/analyses", json=request_body()).json()["share_code"]
    body, sig = code.split(".")
    flipped = body[:10] + ("A" if body[10] != "A" else "B") + body[11:]
    for bad in (
        flipped + "." + sig,                       # payload edited
        body + "." + ("A" if sig[0] != "A" else "B") + sig[1:],  # signature edited
        body[:-5] + "." + sig,                     # truncated by a messenger
        payload_code({"v": 1, "iat": NOW, "r": demo_fields()}, secret="x" * 40),  # other key
        "",
        "not-a-code",
        code + "x",
    ):
        r = open_link(client, bad)
        assert r.status_code == 400, bad[:40]
        assert r.json()["error"]["code"] == "INVALID_SHARE_LINK"


def test_signed_but_rule_breaking_content_is_still_refused(client):
    """A valid signature does not bypass the public-result rules (e.g. a later banned phrase)."""
    bad = payload_code({"v": 1, "iat": NOW, "r": demo_fields(summary="바람기 이야기를 담은 문장")})
    assert open_link(client, bad).status_code == 400
    unknown_type = payload_code({"v": 1, "iat": NOW, "r": demo_fields(type_id="T99")})
    assert open_link(client, unknown_type).status_code == 400
    future_version = payload_code({"v": 2, "iat": NOW, "r": demo_fields()})
    assert open_link(client, future_version).status_code == 400


def test_axes_are_rebuilt_from_the_type_not_trusted_from_the_link(client):
    code = payload_code({"v": 1, "iat": NOW, "r": demo_fields(type_id="T01")})
    r = open_link(client, code)
    assert r.status_code == 200
    assert r.json()["result"]["axes"] == TAXONOMY["T01"]["axes"]


def test_decompression_is_bounded_even_with_a_valid_signature(client, monkeypatch):
    # A payload that is valid once inflated, padded far past the bound with whitespace.
    valid = json.dumps({"v": 1, "iat": NOW, "r": demo_fields()}, ensure_ascii=False)
    bomb = signed(deflate((valid + " " * 2_000_000).encode()))
    assert len(bomb) < MAX_CODE_CHARS
    assert open_link(client, bomb).status_code == 400
    import lovecode.share

    monkeypatch.setattr(lovecode.share, "MAX_PAYLOAD_BYTES", 10**8)
    assert open_link(client, bomb).status_code == 200  # so the bound is what refused it


def test_oversized_codes_are_rejected_before_any_work(client):
    r = open_link(client, "A" * (MAX_CODE_CHARS + 1) + "." + "A" * 22)
    assert r.status_code == 422  # header length limit, before decoding
    assert r.json()["error"]["field"] == "header.x-share-code"


def test_demo_results_get_no_share_code(client):
    assert "share_code" not in client.post("/api/v1/demo-analysis", json={}).json()


def test_sharing_is_off_without_a_long_enough_secret():
    for secret in ("", "too-short", " " * 40):
        codec = ShareCodec(secret)
        assert codec.ready is False
        with pytest.raises(ShareError) as e:
            codec.decode("a.b")
        assert e.value.code == "SHARE_UNAVAILABLE"
    with TestClient(create_app()) as c:
        assert c.get("/api/v1/health").json()["share_ready"] is False
        assert open_link(c, "x").json()["error"]["code"] == "SHARE_UNAVAILABLE"
        assert "share_code" not in c.post("/api/v1/demo-analysis", json={}).json()


def test_rotating_the_secret_invalidates_old_links():
    result = demo_result()
    code = ShareCodec(SECRET).encode(result)
    with pytest.raises(ShareError) as e:
        ShareCodec("n" * 40).decode(code)
    assert e.value.code == "INVALID_SHARE_LINK"


def test_links_without_the_spicy_section_still_open_as_1_0(client):
    fields = demo_fields()
    del fields["spicy"]
    r = open_link(client, payload_code({"v": 1, "iat": NOW, "r": fields}))
    assert r.status_code == 200
    assert r.json()["result"]["schema_version"] == "1.0"
    assert "spicy" not in r.json()["result"]


def test_spicy_section_round_trips_as_1_1_and_keeps_its_wording(client):
    fields = demo_fields()
    fields["spicy"]["titles"]["skinship"]["text"] = "링크를 만들 때의 예전 칭호 문구"
    r = open_link(client, payload_code({"v": 1, "iat": NOW, "r": fields}))
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["schema_version"] == "1.1"
    assert result["spicy"]["titles"]["skinship"] == {"id": "S3", "text": "링크를 만들 때의 예전 칭호 문구"}


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s["titles"]["skinship"].update(id="X9"),           # unknown title
        lambda s: s["titles"]["skinship"].update(id="C1"),           # title from another topic
        lambda s: s["notes"].update(skinship="잠자리 얘기는 따로"),    # explicit wording
        lambda s: s["notes"].pop("reunion"),                         # missing topic
    ],
)
def test_signed_but_invalid_spicy_content_is_refused(client, change):
    fields = demo_fields()
    change(fields["spicy"])
    assert open_link(client, payload_code({"v": 1, "iat": NOW, "r": fields})).status_code == 400
