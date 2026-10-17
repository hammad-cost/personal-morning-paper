"""Publisher logos for the feed's profile pictures.

Each story knows its publisher's site (reuters.com). The logo comes from Google's icon
service, or DuckDuckGo's when Google only has a tiny one, and is cached on disk. Only those
two fixed services are ever fetched, never the domain itself, so a crafted domain can't make
the server call anything else.
"""

import re
import threading
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app import store

SERVICES = [
    "https://www.google.com/s2/favicons?domain={domain}&sz=128",
    "https://icons.duckduckgo.com/ip3/{domain}.ico",
]
GOOD_ENOUGH = 64  # px; stop looking once a logo is at least this big
TIMEOUT = 8
DOMAIN_RE = re.compile(r"^(?=.{4,100}$)([a-z0-9-]+\.)+[a-z]{2,24}$")
NONE = b""  # remembered "no logo" so we don't ask again

_memory: dict[str, bytes] = {}
_lock = threading.Lock()


def domain_of(url: str | None) -> str | None:
    """reuters.com from https://www.reuters.com/x; None for Google News links or junk."""
    if not url:
        return None
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    if not DOMAIN_RE.match(host) or host == "news.google.com":
        return None
    return host


def source_domain(article: dict) -> str | None:
    """The publisher's site: from the feed's <source url>, else the decoded publisher link."""
    for key in ("source_url", "publisher_url", "url"):
        domain = domain_of(article.get(key))
        if domain:
            return domain
    return None


def logos_dir() -> Path:
    return Path(store.STORE_PATH).parent / "logos"


def fetch(url: str) -> bytes | None:
    """GET one icon. Tests replace this."""
    r = httpx.get(url, timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": "Vale/0.2"})
    return r.content if r.status_code == 200 and r.content else None


def _size(data: bytes) -> int:
    try:
        from PIL import Image

        img = Image.open(BytesIO(data))
        return min(img.size)
    except Exception:
        return 0


def _to_png(data: bytes) -> bytes:
    from PIL import Image

    img = Image.open(BytesIO(data))
    if getattr(img, "n_frames", 1) > 1 or img.format == "ICO":
        # .ico files hold several sizes; take the biggest.
        sizes = sorted(img.info.get("sizes", [img.size]), key=lambda s: s[0])
        if img.format == "ICO" and sizes:
            img.size = sizes[-1]
            img.load()
    out = BytesIO()
    img.convert("RGBA").save(out, "PNG")
    return out.getvalue()


def find(domain: str) -> bytes | None:
    """The best logo we can get for a domain, as PNG bytes; None if there is none."""
    best, best_size = None, 0
    for template in SERVICES:
        try:
            data = fetch(template.format(domain=domain))
        except Exception:
            data = None
        size = _size(data) if data else 0
        if size > best_size:
            best, best_size = data, size
        if best_size >= GOOD_ENOUGH:
            break
    if not best:
        return None
    try:
        return _to_png(best)
    except Exception:
        return None


def get(domain: str) -> bytes | None:
    """Cached logo for a validated domain (memory, then disk, then the icon services)."""
    if not DOMAIN_RE.match(domain):
        return None
    with _lock:
        if domain in _memory:
            return _memory[domain] or None
    path = logos_dir() / f"{domain}.png"
    if path.is_file():
        data = path.read_bytes()
    else:
        data = find(domain) or NONE
        if data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    with _lock:
        _memory[domain] = data
    return data or None


def clear_cache() -> None:
    with _lock:
        _memory.clear()
