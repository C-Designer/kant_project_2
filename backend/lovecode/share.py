"""Stateless share links: the result travels inside the link, signed so it cannot be forged.

Nothing is stored anywhere. After an analysis the server compresses the public result and
signs it with LC_SHARE_SECRET; the browser puts that code after `/r#`. The fragment is never
sent to a server by the browser, so it stays out of access logs. The shared page sends the
code in a request header, and this module checks the signature before decompressing.

Trade-offs of having no store: links cannot be revoked or expired, they are long (about
0.7-2 KB), and rotating the secret invalidates every link issued so far.
"""

import base64
import hashlib
import hmac
import json
import re
import time
import zlib
from datetime import UTC, datetime

from .contracts import TAXONOMY, PublicResult, SharedResult
from .settings import settings

VERSION = 1
SIGNATURE_BYTES = 16  # 128-bit truncated HMAC-SHA256
MAX_BODY_CHARS = 10000  # worst case with spicy + reading (1.2) is about 8.1K
MAX_CODE_CHARS = MAX_BODY_CHARS + 1 + 22  # body, ".", 16-byte signature in base64url
MAX_PAYLOAD_BYTES = 24576  # a full-length 1.2 result is about 9.5 KB of JSON
CODE = re.compile(rf"[A-Za-z0-9_-]{{1,{MAX_BODY_CHARS}}}\.[A-Za-z0-9_-]{{22}}")
DAY = 86400
KST = 9 * 3600  # dates are shown in Korea time, so round to the Korean calendar day
# Fields rebuilt on decode instead of being carried in the link (they follow from type_id or
# are fixed literals), which keeps links shorter.
DERIVED = {"axes", "schema_version", "taxonomy_version", "disclaimer_version"}


class ShareError(Exception):
    def __init__(self, code, status, message):
        super().__init__(code)
        self.code, self.status, self.message = code, status, message


UNAVAILABLE = ("SHARE_UNAVAILABLE", 503, "지금은 공유 링크를 열 수 없어요. 잠시 후 다시 시도해 주세요.")
INVALID = (
    "INVALID_SHARE_LINK",
    400,
    "링크가 잘렸거나 더 이상 열 수 없는 링크예요. 받은 링크 전체를 다시 열어 주세요.",
)


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _deflate(data):
    c = zlib.compressobj(9, zlib.DEFLATED, -15)  # raw deflate: no header, smaller links
    return c.compress(data) + c.flush()


def _inflate(data):
    d = zlib.decompressobj(-15)
    out = d.decompress(data, MAX_PAYLOAD_BYTES)
    if d.unconsumed_tail or not d.eof:
        raise ValueError("payload too large or truncated")
    return out


class ShareCodec:
    def __init__(self, secret="", clock=time.time):
        self._secret = secret.strip().encode()
        self._clock = clock

    @classmethod
    def from_settings(cls):
        return cls(settings().share_secret)

    @property
    def ready(self):
        return len(self._secret) >= 32

    def _sign(self, body):
        mac = hmac.new(self._secret, b"lovecode-share.v1." + body, hashlib.sha256)
        return mac.digest()[:SIGNATURE_BYTES]

    def encode(self, result: PublicResult):
        """Signed code for a share link, or None if it would not fit the link limit."""
        fields = result.model_dump(mode="json", exclude=DERIVED, exclude_none=True)
        # Day precision: the payload is readable by anyone holding the link.
        issued = (int(self._clock()) + KST) // DAY * DAY - KST
        payload = {"v": VERSION, "iat": issued, "r": fields}
        body = _deflate(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
        code = _b64(body) + "." + _b64(self._sign(body))
        return code if len(code) <= MAX_CODE_CHARS else None

    def decode(self, code) -> SharedResult:
        if not self.ready:
            raise ShareError(*UNAVAILABLE)
        if len(code) > MAX_CODE_CHARS or not CODE.fullmatch(code):
            raise ShareError(*INVALID)
        body_text, signature_text = code.split(".")
        try:
            body, signature = _unb64(body_text), _unb64(signature_text)
        except ValueError:
            raise ShareError(*INVALID) from None
        # One spelling per link: the decoder ignores stray low bits in the last character.
        if _b64(body) != body_text or _b64(signature) != signature_text:
            raise ShareError(*INVALID)
        # Authenticate before inflating, so an unsigned blob is never decompressed.
        if not hmac.compare_digest(self._sign(body), signature):
            raise ShareError(*INVALID)
        try:
            payload = json.loads(_inflate(body))
            if payload["v"] != VERSION or not isinstance(payload["iat"], int):
                raise ValueError("unknown version")
            fields = payload["r"]
            type_id = fields["type_id"]
            # PublicResult re-runs every output rule, so even a signed link that predates a
            # newly banned phrase is refused rather than shown.
            version = (
                "1.2"
                if fields.get("reading") is not None
                else ("1.1" if fields.get("spicy") is not None else "1.0")
            )
            result = PublicResult(**fields, axes=TAXONOMY[type_id]["axes"], schema_version=version)
            created_at = datetime.fromtimestamp(payload["iat"], UTC)
        except (ValueError, KeyError, TypeError, OverflowError, OSError, zlib.error):
            raise ShareError(*INVALID) from None
        return SharedResult(result=result, created_at=created_at)
