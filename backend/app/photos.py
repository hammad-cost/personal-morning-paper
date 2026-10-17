"""Guarantee a picture for every story, and keep copies on our own server.

For each story, the first layer that works wins:
1. News photo: from the feed or the publisher's preview image (found by images.py).
2. Subject photo: a free Wikipedia/Wikimedia Commons photo of the story's main subject,
   which Gemini names in the same call that writes the summary ("Palo Alto Networks").
3. Topic photo: a free Wikipedia/Commons photo for the section topic, rotated so
   stories in one section don't all share a picture.
4. Vale illustration: drawn here with Pillow (paper, rules, topic name). It needs no network.

Every image is downloaded once, resized to JPEG and stored in data/images/, then served
from /api/images/<file>. That way the web page and the PDF always have it, even if the
publisher later removes or blocks it. Labels always say what the picture is.
"""

import hashlib
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from app import images, store

WIKI_API = "https://en.wikipedia.org/w/api.php"
# Wikimedia asks API clients to identify themselves.
WIKI_UA = {"User-Agent": "Vale/0.2 (student news app; https://github.com/hammad-cost/personal-morning-paper)"}
WIKI_TIMEOUT = 8.0
BAD_IMAGE = re.compile(r"(logo|icon|flag|map|diagram|chart|seal|coat_of_arms|signature|\.svg|wordmark)", re.I)
STOPWORDS = {"the", "and", "for", "with", "news", "new", "of", "in", "on", "a", "an", "to"}
SERVE_PREFIX = "/api/images/"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}\.jpg$")
TOPIC_TTL = 6 * 3600

_topic_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = threading.Lock()


# ---------- storage ----------

def images_dir() -> Path:
    path = Path(store.STORE_PATH).parent / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def local_name(name: str) -> Path | None:
    """Safe path for a served file name, or None (blocks path tricks like ../)."""
    if not NAME_RE.match(name):
        return None
    path = images_dir() / name
    return path if path.is_file() else None


def is_local(url: str | None) -> bool:
    return bool(url) and url.startswith(SERVE_PREFIX)


def _save_jpeg(data: bytes, name: str) -> str | None:
    jpeg = images.to_jpeg(data, max_width=1200)
    if not jpeg:
        return None
    (images_dir() / name).write_bytes(jpeg.getvalue())
    return name


def save_remote(url: str) -> str | None:
    """Download an image once and keep a JPEG copy; returns the file name."""
    name = hashlib.sha1(url.encode("utf-8")).hexdigest() + ".jpg"
    if (images_dir() / name).is_file():
        return name
    data = images.fetch_image(url)
    return _save_jpeg(data, name) if data else None


def read_local(url: str) -> bytes | None:
    if not is_local(url):
        return None
    path = local_name(url[len(SERVE_PREFIX):])
    return path.read_bytes() if path else None


def clear() -> None:
    """Dev reset: remove stored pictures."""
    for f in images_dir().glob("*.jpg"):
        f.unlink(missing_ok=True)
    _topic_cache.clear()


# ---------- Wikipedia / Wikimedia Commons ----------

def wiki_search(query: str, limit: int) -> list[dict]:
    """Articles matching `query` that have a FREE lead image: [{title, url}] best first. Tests replace this."""
    r = httpx.get(WIKI_API, timeout=WIKI_TIMEOUT, headers=WIKI_UA, params={
        "action": "query", "format": "json", "generator": "search", "gsrsearch": query, "gsrnamespace": 0,
        "gsrlimit": limit, "prop": "pageimages", "piprop": "thumbnail", "pithumbsize": 960, "pilicense": "free",
    })
    r.raise_for_status()
    pages = sorted((r.json().get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    return [{"title": p["title"], "url": p["thumbnail"]["source"]} for p in pages if p.get("thumbnail")]


def _word_list(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOPWORDS]


def _same(a: str, b: str) -> bool:
    """agents ~ agent, tech ~ technology."""
    return a == b or a.rstrip("s") == b.rstrip("s") or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


def title_matches(title: str, query: str, strict: bool = False) -> bool:
    """Is this Wikipedia page really about `query`?

    strict (story subjects): the title must be exactly the subject (a bracketed
    disambiguation is allowed), so "Albert Heijn Jr." or "SpaceXAI" never stand in
    for "Albert Heijn" or "SpaceX".
    loose (section topics): every topic word appears somewhere in the title.
    """
    if strict:
        # Exactly the subject's own page; only a bracketed disambiguation may follow ("Starship (spacecraft)").
        # Every word counts here, even short ones, so "Albert Heijn Jr." is not "Albert Heijn".
        def tokens(text):
            return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w != "the"]

        want, got = tokens(query), tokens(re.sub(r"\s*\(.*\)\s*$", "", title))
        return bool(want) and len(got) == len(want) and all(g.rstrip("s") == w.rstrip("s") for g, w in zip(got, want))
    wanted, have = _word_list(query), _word_list(title)
    if not wanted or not have:
        return False
    return all(any(_same(h, w) for h in have) for w in wanted)


def _usable(hit: dict) -> bool:
    return not BAD_IMAGE.search(hit["url"].split("?")[0]) and "/wikipedia/commons/" in hit["url"]


def subject_photo(subject: str) -> dict | None:
    subject = (subject or "").strip()
    if len(subject) < 3:
        return None
    for hit in wiki_search(subject, 5):
        if _usable(hit) and title_matches(hit["title"], subject, strict=True):
            return hit
    return None


def topic_photos(topic: str, hint: str = "") -> list[dict]:
    """Free photos for a section, only from pages whose title matches the topic or the AI's hint
    (e.g. Space -> "Spaceflight"). Hint matches come first. Cached."""
    key = f"{topic.lower()}|{hint.lower()}"
    cached = _topic_cache.get(key)
    if cached and time.monotonic() - cached[0] < TOPIC_TTL:
        return cached[1]
    hits, seen = [], set()
    for query in [q for q in (hint, topic) if q]:
        for h in _attempt(lambda: wiki_search(query, 15)) or []:
            if h["url"] not in seen and _usable(h) and title_matches(h["title"], query):
                seen.add(h["url"])
                hits.append(h)
    _topic_cache[key] = (time.monotonic(), hits)
    return hits


# ---------- layer 4: drawn locally ----------

def vale_illustration(topic: str) -> str:
    """A calm, newspaper-style picture with the topic name. Always works."""
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFont

    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:40] or "news"
    name = f"vale-{slug}.jpg"
    if (images_dir() / name).is_file():
        return name
    w, h = 1200, 675
    img = Image.new("RGB", (w, h), (250, 247, 242))
    d = ImageDraw.Draw(img)

    def font(size):
        try:
            return ImageFont.load_default(size=size)
        except Exception:
            return ImageFont.load_default()

    ink, muted, accent = (26, 25, 23), (92, 88, 82), (185, 56, 41)
    # Fine hatching in the background, like an engraving.
    for x in range(-h, w, 18):
        d.line([(x, h), (x + h, 0)], fill=(236, 231, 222), width=2)
    d.rectangle([40, 40, w - 40, h - 40], outline=ink, width=4)
    d.line([(60, 150), (w - 60, 150)], fill=ink, width=3)
    d.line([(60, 158), (w - 60, 158)], fill=ink, width=1)
    d.line([(60, h - 158), (w - 60, h - 158)], fill=ink, width=1)
    d.line([(60, h - 150), (w - 60, h - 150)], fill=ink, width=3)
    title = topic.upper()[:28]
    size = 110
    while size > 40 and d.textlength(title, font=font(size)) > w - 160:
        size -= 6
    d.text((w / 2, h / 2), title, font=font(size), fill=ink, anchor="mm")
    d.text((w / 2, 100), "VALE", font=font(40), fill=accent, anchor="mm")
    d.text((w / 2, h - 100), "TODAY'S SECTION", font=font(28), fill=muted, anchor="mm")
    out = BytesIO()
    img.save(out, "JPEG", quality=85)
    (images_dir() / name).write_bytes(out.getvalue())
    return name


# ---------- the chain ----------

def _attempt(fn):
    try:
        return fn()
    except Exception:
        return None


def _stored(kind: str, credit: str, name: str, source: str | None) -> dict:
    return {"image_kind": kind, "image_credit": credit, "image_file": name, "image_source_url": source}


def own_picture(article: dict, subject: str = "") -> dict | None:
    """Layers 1-2: a picture of this story itself (news photo or its subject)."""
    source = article.get("source_name") or "the publisher"
    if article.get("image_url") and not is_local(article["image_url"]):
        name = _attempt(lambda: save_remote(article["image_url"]))
        if name:
            return _stored("news", f"Photo: {source}", name, article["image_url"])
    if subject:
        hit = _attempt(lambda: subject_photo(subject))
        name = hit and _attempt(lambda: save_remote(hit["url"]))
        if name:
            return _stored("subject", f"Photo: Wikimedia Commons · {hit['title']}", name, hit["url"])
    return None


def topic_picture(article: dict, pool: list[dict], taken: set[str]) -> dict:
    """Layers 3-4: an unused topic photo if possible, else any topic photo, else a Vale illustration."""
    for prefer_unused in (True, False):
        for hit in pool:
            if prefer_unused and hit["url"] in taken:
                continue
            name = _attempt(lambda: save_remote(hit["url"]))
            if name:
                taken.add(hit["url"])
                return _stored("topic", f"Topic photo: Wikimedia Commons · {hit['title']}", name, hit["url"])
    topic = article.get("topic") or "News"
    return _stored("illustration", f"Vale illustration · {topic}", vale_illustration(topic), None)


def ensure(articles: list[dict], subjects: dict[str, str] | None = None, topic_hints: dict[str, str] | None = None) -> None:
    """Give every story in `articles` a stored picture (in place). Stories that already have one are kept."""
    subjects = subjects or {}
    hints = {k.lower(): v for k, v in (topic_hints or {}).items()}
    todo = [a for a in articles if not is_local(a.get("image_url"))]
    if not todo:
        return
    # Pass 1, in parallel: a photo of the story itself.
    with ThreadPoolExecutor(max_workers=8) as pool:
        found = dict(zip([a["id"] for a in todo], pool.map(lambda a: own_picture(a, subjects.get(a["id"], "")), todo)))
    # Pass 2: topic photos only for stories still without one, so a section doesn't repeat a picture.
    need = [a for a in todo if not found[a["id"]]]
    topics = sorted({a.get("topic") or "News" for a in need})
    with ThreadPoolExecutor(max_workers=4) as pool:
        pools = dict(zip(topics, pool.map(lambda t: _attempt(lambda: topic_photos(t, hints.get(t.lower(), ""))) or [], topics)))
    taken: dict[str, set[str]] = {t: set() for t in topics}
    for a in need:
        topic = a.get("topic") or "News"
        found[a["id"]] = topic_picture(a, pools[topic], taken[topic])
    for a in todo:
        f = found[a["id"]]
        a["image_url"] = SERVE_PREFIX + f["image_file"]
        a["image_credit"] = f["image_credit"]
        a["image_kind"] = f["image_kind"]
        a["image_source_url"] = f["image_source_url"]
