"""Issue log: one JSON line per noteworthy event, collected by the platform (Vercel runtime logs).

The service keeps no database, so the platform log collector is the only store. Every field is
allow-listed below; request bodies, birth data, MBTI, questions, headers and API keys never reach
this module. Callers pass short machine codes, not free text.

Levels (routing, not mood):
- info: an analysis finished as designed (`analysis.completed`).
- warning: handled and expected under load — busy, daily limit (`analysis.busy`, `analysis.daily_limit`).
- error: the user saw a failure — provider/config/unhandled errors.

Read: vercel logs --project kant-lovecode-api --scope zerocode-studio --json | grep lovecode.issue
"""

import contextvars
import json
import logging
import os
import re
import sys
import uuid
from datetime import UTC, datetime

# Fixed vocabulary of event keys; extend here, not at call sites.
EVENTS = {
    "analysis.completed",
    "analysis.busy",
    "analysis.daily_limit",
    "analysis.provider_failed",
    "analysis.config_failed",
    "request.unhandled",
}
FIELDS = {  # allow-list of detail fields
    "http_status",
    "provider_error_type",
    "provider_error_code",
    "provider_request_id",
    "ratelimit_remaining_requests",
    "ratelimit_remaining_tokens",
    "exception",
    "stage",
    "duration_ms",
}
_SAFE = re.compile(r"^[A-Za-z0-9_.:/\-]{1,96}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_:\-]{1,128}$")

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

_log = logging.getLogger("lovecode.issue")
if not _log.handlers:
    out, err = logging.StreamHandler(sys.stdout), logging.StreamHandler(sys.stderr)
    out.addFilter(lambda r: r.levelno < logging.WARNING)
    err.setLevel(logging.WARNING)  # Vercel marks stderr lines as warnings/errors
    for h in (out, err):
        h.setFormatter(logging.Formatter("%(message)s"))
        _log.addHandler(h)
    _log.setLevel(logging.INFO)
    _log.propagate = False


def environment():
    return os.environ.get("VERCEL_ENV") or os.environ.get("LC_ENV") or "local"


def new_request_id(inbound: str | None = None) -> str:
    """Adopt Vercel's edge id (set by the platform, not the client) when it is well formed."""
    if inbound and _SAFE_ID.match(inbound):
        return inbound
    return uuid.uuid4().hex


def safe(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int | float):
        return value
    text = str(value)
    return text if _SAFE.match(text) else "[unprintable]"


def issue(level: str, event: str, code: str, route: str = "", **detail) -> dict:
    assert event in EVENTS, event
    record = {
        "log": "lovecode.issue",
        "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "level": level,
        "env": environment(),
        "event": event,
        "code": safe(code),
        "request_id": request_id_var.get() or "-",
        "route": safe(route) if route else None,
        **{k: safe(v) for k, v in detail.items() if k in FIELDS and v is not None},
    }
    record["fingerprint"] = ":".join(
        str(x) for x in (event, record["code"], record.get("provider_error_code", "")) if x
    )
    # Handler errors are reported by logging.Handler.handleError, never raised into the request.
    _log.log(getattr(logging, level.upper()), json.dumps(record, ensure_ascii=False))
    return record
