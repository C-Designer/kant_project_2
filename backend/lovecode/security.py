import base64
import hashlib
import hmac
import json
import time
import uuid

from .contracts import PublicResult
from .settings import settings


class TicketError(Exception):
    def __init__(self, expired=False):
        self.expired = expired


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def digest(token):
    return hashlib.sha256(token.encode()).digest()


def issue(result, versions=None):
    now = int(time.time())
    payload = {
        "version": 1,
        "analysis_id": str(uuid.uuid4()),
        "result": result.model_dump(),
        "versions": versions
        or {
            "generator": "static-fixture-v1",
            "classifier": "not-trained",
            "calendar": "not-activated",
        },
        "issued_at": now,
        "expires_at": now + 600,
        "audience": "save-result",
        "key_id": "local-v1",
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    sig = hmac.new(settings().signing_key.encode(), raw, hashlib.sha256).digest()
    return payload, b64(raw) + "." + b64(sig)


def verify(ticket):
    try:
        body, signature = ticket.split(".")
        raw = unb64(body)
        expected = hmac.new(settings().signing_key.encode(), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, unb64(signature)):
            raise ValueError()
        p = json.loads(raw)
        if p["version"] != 1 or p["key_id"] != "local-v1" or p["audience"] != "save-result":
            raise ValueError()
        uuid.UUID(p["analysis_id"])
        if p["expires_at"] - p["issued_at"] != 600 or p["issued_at"] > time.time() + 5:
            raise ValueError()
        if p["expires_at"] <= time.time():
            raise TicketError(expired=True)
        PublicResult.model_validate(p["result"])
        return p
    except TicketError:
        raise
    except (ValueError, KeyError, TypeError):
        raise TicketError() from None
