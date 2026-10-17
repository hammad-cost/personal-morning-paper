"""Keep story pictures in Supabase Storage so they survive server restarts.

Online hosts like Render's free plan wipe the disk on every restart or deploy. When
SUPABASE_URL and SUPABASE_SECRET_KEY are set, every stored picture is also uploaded to a
private bucket, and read back from there when the local copy is gone. The bucket is
created on first use. Pictures are still served by our own /api/images/<file> endpoint,
so their addresses never change. Without Supabase, the local disk is used alone.
"""

import os
import threading

import httpx

from app import store

TIMEOUT = 15
_ready = False
_lock = threading.Lock()


def bucket() -> str:
    return os.getenv("SUPABASE_IMAGES_BUCKET", "vale-images").strip() or "vale-images"


def enabled() -> bool:
    return store.supabase_storage() is not None


def _headers(content_type: str | None = None) -> dict:
    _, key = store.supabase_storage()
    headers = store._headers(key)
    if content_type:
        headers["Content-Type"] = content_type
    else:
        headers.pop("Content-Type", None)
    return headers


def ensure_bucket() -> None:
    """Create the private bucket once per server run (an existing bucket is fine)."""
    global _ready
    with _lock:
        if _ready:
            return
        url, _ = store.supabase_storage()
        r = httpx.post(f"{url}/storage/v1/bucket", headers=_headers("application/json"), timeout=TIMEOUT,
                       json={"id": bucket(), "name": bucket(), "public": False})
        if r.status_code >= 400 and "exist" not in r.text.lower():
            r.raise_for_status()
        _ready = True


def upload(name: str, data: bytes, content_type: str = "image/jpeg") -> None:
    ensure_bucket()
    url, _ = store.supabase_storage()
    r = httpx.post(f"{url}/storage/v1/object/{bucket()}/{name}", content=data, timeout=TIMEOUT,
                   headers={**_headers(content_type), "x-upsert": "true", "cache-control": "31536000"})
    r.raise_for_status()


def download(name: str) -> bytes | None:
    url, _ = store.supabase_storage()
    r = httpx.get(f"{url}/storage/v1/object/{bucket()}/{name}", headers=_headers(), timeout=TIMEOUT)
    if r.status_code in (400, 404):
        return None
    r.raise_for_status()
    return r.content


def reset() -> None:
    """Tests: forget that the bucket was checked."""
    global _ready
    _ready = False
