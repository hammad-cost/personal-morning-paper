"""Signed links for emails: download a PDF or unsubscribe without signing in.

A link carries (purpose, reader id, edition id, expiry) plus an HMAC signature, so it
can't be guessed or edited to open someone else's paper, and it stops working after
it expires.
"""

import base64
import hashlib
import hmac
import json
import os
import time

PDF_LINK_DAYS = 7
UNSUBSCRIBE_DAYS = 365


class BadLink(ValueError):
    pass


def _secret() -> bytes:
    # A dedicated LINK_SECRET is best; otherwise derive one from a server secret that
    # already exists, so links keep working across restarts.
    raw = (os.getenv("LINK_SECRET") or os.getenv("SUPABASE_SECRET_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
    if not raw:
        raise RuntimeError("Set LINK_SECRET (or another server secret) to sign email links.")
    return hashlib.sha256(b"vale-links:" + raw.encode()).digest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make(purpose: str, uid: str, edition_id: str = "", days: int = PDF_LINK_DAYS) -> str:
    payload = _b64(json.dumps({"p": purpose, "u": uid, "e": edition_id, "x": int(time.time()) + days * 86400},
                              separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest()[:18])
    return f"{payload}.{sig}"


def read(token: str, purpose: str) -> dict:
    """{"u": reader id, "e": edition id} for a valid, unexpired link of this purpose."""
    try:
        payload, sig = token.split(".", 1)
        good = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest()[:18])
        if not hmac.compare_digest(sig, good):
            raise BadLink("link signature is wrong")
        data = json.loads(_unb64(payload))
    except BadLink:
        raise
    except Exception as exc:
        raise BadLink("link is damaged") from exc
    if data.get("p") != purpose:
        raise BadLink("link is for something else")
    if data.get("x", 0) < time.time():
        raise BadLink("link has expired")
    return data
