"""Who is asking? Sign-in is handled by Supabase Auth in the browser; the browser sends its
access token with every request, and this module turns it into a user id.

Without SUPABASE_URL the app runs in local mode: one reader, no sign-in (development,
tests and the original single-reader demo).

Tokens are checked by asking Supabase Auth itself (GET /auth/v1/user), which works with
every Supabase signing setup. A verified token is cached until shortly before it expires,
so this costs one call per sign-in session, not one per request.
"""

import hashlib
import os
import threading
import time

import httpx

from app.store import LOCAL_USER

CACHE_SECONDS = 10 * 60
_cache: dict[str, tuple[float, str]] = {}
_guard = threading.Lock()


class NotSignedIn(PermissionError):
    pass


def auth_url() -> str:
    return os.getenv("SUPABASE_URL", "").strip().rstrip("/")


def enabled() -> bool:
    return bool(auth_url())


def _public_key() -> str:
    # The publishable (anon) key identifies the project to Supabase Auth; it is not secret.
    return os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip() or os.getenv("SUPABASE_SECRET_KEY", "").strip()


def fetch_user(token: str) -> dict:
    """Ask Supabase who owns this token. Tests replace this."""
    r = httpx.get(f"{auth_url()}/auth/v1/user", timeout=10,
                  headers={"apikey": _public_key(), "Authorization": f"Bearer {token}"})
    if r.status_code in (401, 403):
        raise NotSignedIn("session expired or invalid")
    r.raise_for_status()
    return r.json()


def user_id_for(authorization: str | None) -> str:
    """The reader's id from an 'Authorization: Bearer <token>' header."""
    if not enabled():
        return LOCAL_USER
    if not authorization or not authorization.lower().startswith("bearer "):
        raise NotSignedIn("please sign in")
    token = authorization.split(" ", 1)[1].strip()
    key = hashlib.sha256(token.encode()).hexdigest()
    with _guard:
        hit = _cache.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
    try:
        user = fetch_user(token)
    except NotSignedIn:
        raise
    except Exception as exc:
        raise NotSignedIn("could not verify your session") from exc
    uid = user.get("id")
    if not uid:
        raise NotSignedIn("session has no user")
    with _guard:
        _cache[key] = (time.monotonic() + CACHE_SECONDS, uid)
    return uid


def clear_cache() -> None:
    with _guard:
        _cache.clear()
