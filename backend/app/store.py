"""The only module that touches store.json.

All reads and writes go through load/save/update/reset so the rest of the
app never handles the file directly.
"""

import copy
import json
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

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

_lock = threading.RLock()


def defaults() -> dict:
    return copy.deepcopy(DEFAULT_STORE)


def _read() -> dict:
    if not STORE_PATH.exists():
        data = defaults()
        _write(data)
        return data
    with STORE_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    # Fill any keys added after the file was first created.
    for key, value in DEFAULT_STORE.items():
        data.setdefault(key, copy.deepcopy(value))
    for key, value in DEFAULT_STORE["user"].items():
        data["user"].setdefault(key, copy.deepcopy(value))
    return data


def _write(data: dict) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temp file then rename, so a crash never leaves half a file.
    fd, tmp = tempfile.mkstemp(dir=STORE_PATH.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STORE_PATH)


def load() -> dict:
    with _lock:
        return _read()


def save(data: dict) -> None:
    with _lock:
        _write(data)


def update(fn: Callable[[dict], None]) -> dict:
    """Load, apply fn to the data in place, save, and return the new data."""
    with _lock:
        data = _read()
        fn(data)
        _write(data)
        return data


def reset() -> dict:
    with _lock:
        data = defaults()
        _write(data)
        return data
