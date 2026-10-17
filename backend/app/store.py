"""The only module that touches reader data.

Every reader has one document: {"user": {...}, "editions": [...], "signals": [...]}.
All reads and writes go through load/save/update/reset so the rest of the app never
handles storage directly.

Where a document lives:
- the "local" reader (no sign-in, development and tests): data/store.json
- signed-in readers, when Supabase is configured: one row each in the
  `vale_readers` table (see supabase/schema.sql), read and written with the
  server's secret key over Supabase's REST API
- signed-in readers without Supabase storage (development): data/users/<id>.json
"""

import copy
import json
import os
import re
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

import httpx

LOCAL_USER = "local"

STORE_PATH = Path(
    os.getenv("STORE_PATH", Path(__file__).resolve().parent.parent / "data" / "store.json")
)

DEFAULT_STORE = {
    "user": {
        "onboarded": False,
        "name": "",
        "paper_title": "",
        "bio": "",
        "topic_weights": {},
        "source_weights": {},
        "created_at": None,
    },
    "editions": [],
    "signals": [],
}

_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()
_USER_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def defaults() -> dict:
    return copy.deepcopy(DEFAULT_STORE)


def _lock(uid: str) -> threading.RLock:
    with _locks_guard:
        return _locks.setdefault(uid, threading.RLock())


def _fill_defaults(data: dict) -> dict:
    # Fill any keys added after the document was first created.
    for key, value in DEFAULT_STORE.items():
        data.setdefault(key, copy.deepcopy(value))
    for key, value in DEFAULT_STORE["user"].items():
        data["user"].setdefault(key, copy.deepcopy(value))
    return data


# ---------- file backend ----------

def _path_for(uid: str) -> Path:
    if uid == LOCAL_USER:
        return Path(STORE_PATH)
    if not _USER_ID.match(uid):
        raise ValueError("invalid user id")
    return Path(STORE_PATH).parent / "users" / f"{uid}.json"


def _read_file(path: Path) -> dict | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _write_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file then rename, so a crash never leaves half a file.
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# ---------- Supabase backend ----------

TABLE = "vale_readers"


def supabase_storage() -> tuple[str, str] | None:
    """(project URL, secret key) when signed-in readers are stored in Supabase."""
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    return (url, key) if url and key else None


def _headers(key: str) -> dict:
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):  # legacy service_role keys are JWTs and also go in Authorization
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _read_supabase(uid: str) -> dict | None:
    url, key = supabase_storage()
    r = httpx.get(f"{url}/rest/v1/{TABLE}", params={"user_id": f"eq.{uid}", "select": "data"},
                  headers=_headers(key), timeout=10)
    r.raise_for_status()
    rows = r.json()
    return rows[0]["data"] if rows else None


def _write_supabase(uid: str, data: dict) -> None:
    url, key = supabase_storage()
    r = httpx.post(f"{url}/rest/v1/{TABLE}", params={"on_conflict": "user_id"},
                   headers={**_headers(key), "Prefer": "resolution=merge-duplicates,return=minimal"},
                   json={"user_id": uid, "data": data}, timeout=10)
    r.raise_for_status()


# ---------- public API ----------

def _read(uid: str) -> dict:
    if uid != LOCAL_USER and supabase_storage():
        data = _read_supabase(uid)
    else:
        data = _read_file(_path_for(uid))
    if data is None:
        data = defaults()
        _write(uid, data)
        return data
    return _fill_defaults(data)


def _write(uid: str, data: dict) -> None:
    if uid != LOCAL_USER and supabase_storage():
        _write_supabase(uid, data)
    else:
        _write_file(_path_for(uid), data)


def load(uid: str = LOCAL_USER) -> dict:
    with _lock(uid):
        return _read(uid)


def save(data: dict, uid: str = LOCAL_USER) -> None:
    with _lock(uid):
        _write(uid, data)


def update(fn: Callable[[dict], None], uid: str = LOCAL_USER) -> dict:
    """Load, apply fn to the data in place, save, and return the new data."""
    with _lock(uid):
        data = _read(uid)
        fn(data)
        _write(uid, data)
        return data


def reset(uid: str = LOCAL_USER) -> dict:
    with _lock(uid):
        data = defaults()
        _write(uid, data)
        return data
