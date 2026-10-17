"""News photos for the chosen stories, best effort.

1. RSS: many feeds (BBC, Ars Technica, The Verge) carry an image in media tags or HTML.
2. Google News links are decoded to the publisher's own URL, then the article's
   preview image (og:image / twitter:image) is read from the first part of the page.

Everything here may fail (paywalls, bot blocks, timeouts); a story without a photo just
prints as text. Images never affect which stories are chosen.
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, wait
from io import BytesIO
from urllib.parse import quote, urljoin, urlsplit

import httpx

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 6.0
HEAD_BYTES = 400_000  # og:image lives in <head>; never read whole pages
MAX_IMAGE_BYTES = 3_000_000
BUDGET_SECONDS = 12  # total time for all stories in one edition
LINK_BUDGET_SECONDS = 15  # decoding the chosen stories' Google News links (about 4 s each, in parallel)
LINK_WORKERS = 20  # one per story in a paper
CACHE_TTL = 30 * 60
GN_BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"

_cache: dict[str, tuple[float, dict]] = {}


# ---------- small helpers (tests replace the network ones) ----------

def _safe_http_url(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    url = url.strip().replace("&amp;", "&")
    if urlsplit(url).scheme not in ("http", "https"):
        return None
    # Site logos and tracking pixels are not news photos.
    if re.search(r"(logo|favicon|sprite|pixel|placeholder|default-image)", urlsplit(url).path, re.I):
        return None
    return url


def fetch_text(url: str, limit: int = HEAD_BYTES) -> tuple[str, str]:
    """GET up to `limit` bytes; returns (final_url, text)."""
    with httpx.Client(headers=UA, timeout=TIMEOUT, follow_redirects=True) as client:
        with client.stream("GET", url) as r:
            r.raise_for_status()
            chunks, size = [], 0
            for chunk in r.iter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= limit:
                    break
            return str(r.url), b"".join(chunks).decode(r.encoding or "utf-8", errors="replace")


def post_form(url: str, body: str) -> str:
    r = httpx.post(url, content=body, timeout=TIMEOUT, headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    r.raise_for_status()
    return r.text


_image_cache: dict[str, bytes] = {}
_link_cache: dict[str, str] = {}  # Google News link -> publisher link (kept even if a photo lookup times out)
IMAGE_CACHE_SIZE = 60


def fetch_image(url: str) -> bytes | None:
    """Download an image for the PDF (size-capped, cached). None on any failure."""
    if url in _image_cache:
        return _image_cache[url]
    data = _download_image(url)
    if data:
        if len(_image_cache) >= IMAGE_CACHE_SIZE:
            _image_cache.pop(next(iter(_image_cache)))  # drop the oldest
        _image_cache[url] = data
    return data


# Wikimedia refuses generic browser user agents; API clients must identify themselves.
WIKIMEDIA_UA = {"User-Agent": "Vale/0.2 (student news app; https://github.com/hammad-cost/personal-morning-paper)"}


def _download_image(url: str) -> bytes | None:
    headers = WIKIMEDIA_UA if urlsplit(url).netloc.endswith("wikimedia.org") else UA
    try:
        with httpx.Client(headers=headers, timeout=TIMEOUT, follow_redirects=True) as client:
            with client.stream("GET", url) as r:
                r.raise_for_status()
                if not r.headers.get("content-type", "image/").startswith("image/"):
                    return None
                data = b""
                for chunk in r.iter_bytes():
                    data += chunk
                    if len(data) > MAX_IMAGE_BYTES:
                        return None
                return data
    except Exception:
        return None


# ---------- 1. images already in the RSS ----------

def _upgrade(url: str) -> str:
    # BBC thumbnails come at 240px; their image service serves larger sizes by path.
    return re.sub(r"(ichef\.bbci\.co\.uk/[^/]+/[^/]+/)\d+(/)", r"\g<1>800\2", url)


def rss_image(entry) -> str | None:
    """Best image URL carried by a feedparser entry, if any."""
    candidates = []
    for m in entry.get("media_content") or []:
        if (m.get("medium") == "image" or str(m.get("type", "")).startswith("image/") or not m.get("type")):
            candidates.append((int(m.get("width") or 0), m.get("url")))
    for m in entry.get("media_thumbnail") or []:
        candidates.append((int(m.get("width") or 0), m.get("url")))
    for enc in entry.get("enclosures") or []:
        if str(enc.get("type", "")).startswith("image/"):
            candidates.append((0, enc.get("href") or enc.get("url")))
    for url in sorted(candidates, key=lambda c: -c[0]):
        safe = _safe_http_url(url[1])
        if safe:
            return _upgrade(safe)
    html = (entry.get("summary") or "") + "".join(c.get("value", "") for c in entry.get("content") or [])
    m = re.search(r"<img[^>]+src=[\"']([^\"']+)[\"']", html, re.I)
    return _upgrade(_safe_http_url(m.group(1))) if m and _safe_http_url(m.group(1)) else None


# ---------- 2. Google News link -> publisher URL ----------

def is_google_news(url: str) -> bool:
    return urlsplit(url).netloc.endswith("news.google.com") and "/articles/" in urlsplit(url).path


def decode_google_news(url: str) -> str | None:
    """Turn a news.google.com/rss/articles/... link into the publisher's URL (Google's own decoder flow)."""
    art_id = urlsplit(url).path.rstrip("/").split("/")[-1]
    _, page = fetch_text(url, limit=2_000_000)  # the signature sits near the end of this page
    sg = re.search(r'data-n-a-sg="([^"]+)"', page)
    ts = re.search(r'data-n-a-ts="([^"]+)"', page)
    if not (sg and ts):
        return None
    inner = (
        '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
        f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{art_id}",{ts.group(1)},"{sg.group(1)}"]'
    )
    text = post_form(GN_BATCH_URL, "f.req=" + quote(json.dumps([[["Fbv4je", inner]]])))
    decoded = json.loads(json.loads(text.split("\n\n")[1])[0][2])[1]
    return decoded if _safe_http_url(decoded) and not is_google_news(decoded) else None


# ---------- 3. publisher page -> preview image ----------

_META = [
    re.compile(r"<meta[^>]+(?:property|name)=[\"'](?:og:image(?::secure_url)?|twitter:image(?::src)?)[\"'][^>]*content=[\"']([^\"']+)", re.I),
    re.compile(r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]*(?:property|name)=[\"'](?:og:image(?::secure_url)?|twitter:image(?::src)?)[\"']", re.I),
]


def og_image(url: str) -> str | None:
    final_url, html = fetch_text(url)
    for pattern in _META:
        m = pattern.search(html)
        if m:
            return _safe_http_url(urljoin(final_url, m.group(1)))
    return None


# ---------- per story ----------

def find_for(article: dict) -> dict:
    """{'image_url': ..., 'publisher_url': ...} for one story; empty on failure. Cached."""
    key = article["url"]
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL:
        return hit[1]
    found: dict = {}
    try:
        page_url = article["url"]
        if is_google_news(page_url):
            publisher = publisher_link(page_url)
            if publisher:
                found["publisher_url"] = publisher
                page_url = publisher
            else:
                page_url = None
        if page_url and not article.get("image_url"):
            image = og_image(page_url)
            if image:
                found["image_url"] = image
    except Exception:
        pass  # paywall, bot block, timeout: no photo for this one
    _cache[key] = (time.monotonic(), found)
    return found


def publisher_link(url: str) -> str | None:
    """Cached Google News decode; None when Google won't say."""
    if url in _link_cache:
        return _link_cache[url]
    publisher = decode_google_news(url)
    if publisher:
        _link_cache[url] = publisher
    return publisher


def _try_link(url: str) -> str | None:
    try:
        return publisher_link(url)
    except Exception:
        return None


def resolve_links(articles: list[dict], budget: float = LINK_BUDGET_SECONDS) -> None:
    """Give the chosen stories their publisher link (for citations, QR codes and Read original)."""
    todo = [a for a in articles if not a.get("publisher_url") and is_google_news(a.get("url", ""))]
    for a in todo:
        if a["url"] in _link_cache:
            a["publisher_url"] = _link_cache[a["url"]]
    todo = [a for a in todo if not a.get("publisher_url")]
    if not todo:
        return
    pool = ThreadPoolExecutor(max_workers=LINK_WORKERS)
    futures = {pool.submit(_try_link, a["url"]): a for a in todo}
    done, _ = wait(futures, timeout=budget)
    for fut in done:
        if fut.result():
            futures[fut]["publisher_url"] = fut.result()
    pool.shutdown(wait=False, cancel_futures=True)


def enrich(articles: list[dict], budget: float = BUDGET_SECONDS) -> None:
    """Add image_url / publisher_url to stories in place, in parallel, within a time budget."""
    todo = [a for a in articles if not a.get("image_url") or is_google_news(a["url"])]
    if not todo:
        return
    pool = ThreadPoolExecutor(max_workers=8)
    futures = {pool.submit(find_for, a): a for a in todo}
    done, _ = wait(futures, timeout=budget)
    for fut in done:
        found = fut.result()
        article = futures[fut]
        for key, value in found.items():
            if key == "image_url" and article.get("image_url"):
                continue  # an RSS image is already there
            article[key] = value
    pool.shutdown(wait=False, cancel_futures=True)


def clear_cache() -> None:
    _cache.clear()
    _image_cache.clear()
    _link_cache.clear()


# ---------- PDF helper ----------

def to_jpeg(data: bytes, max_width: int = 900) -> BytesIO | None:
    """Resize and re-encode an image for the PDF; None if Pillow cannot read it."""
    try:
        from PIL import Image

        img = Image.open(BytesIO(data))
        img.load()
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        if img.width > max_width:
            img = img.resize((max_width, int(img.height * max_width / img.width)))
        if img.width < 120 or img.height < 80:
            return None  # icons and spacers
        out = BytesIO()
        img.save(out, "JPEG", quality=72, optimize=True)
        out.seek(0)
        return out
    except Exception:
        return None
