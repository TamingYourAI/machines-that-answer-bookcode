"""Signed links: one purpose, one subject, an expiry, and nothing else.

A link sent by text is a door into the business. It opens one thing (upload photos to one claim,
see one claim's status), for a limited time, and it carries no personal data in the clear
(builders' Chapter 9, link safety). The signature is HMAC-SHA256 over the payload.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


PATHS = {"upload": "/u/", "status": "/s/", "docs": "/d/"}


class Links:
    def __init__(self, secret: str | bytes, base_url: str = "http://localhost:8080"):
        self.secret = secret.encode() if isinstance(secret, str) else secret
        self.base_url = base_url.rstrip("/")

    def token(self, purpose: str, subject: str, ttl_s: int = 72 * 3600,
              extra: dict | None = None, now: float | None = None) -> str:
        now = now if now is not None else time.time()
        payload = {"p": purpose, "s": subject, "e": int(now + ttl_s), **(extra or {})}
        body = _b64(json.dumps(payload, separators=(",", ":")).encode())
        sig = _b64(hmac.new(self.secret, body.encode(), hashlib.sha256).digest()[:16])
        return f"{body}.{sig}"

    def url(self, purpose: str, subject: str, ttl_s: int = 72 * 3600,
            extra: dict | None = None) -> str:
        return self.base_url + PATHS.get(purpose, "/l/") + self.token(purpose, subject, ttl_s,
                                                                        extra)

    def verify(self, token: str, purpose: str, now: float | None = None) -> dict | None:
        try:
            body, sig = token.split(".", 1)
            want = _b64(hmac.new(self.secret, body.encode(), hashlib.sha256).digest()[:16])
            if not hmac.compare_digest(sig, want):
                return None
            payload = json.loads(_unb64(body))
        except (ValueError, json.JSONDecodeError):
            return None
        now = now if now is not None else time.time()
        if payload.get("p") != purpose or payload.get("e", 0) < now:
            return None
        return payload
