"""Gather candidate articles from Google News RSS (one query per topic) plus fixed fallback feeds.

Only RSS text is used (title + description, max 600 chars); full pages are never scraped.
"""

import hashlib
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from urllib.parse import quote_plus, urlsplit, urlunsplit

import feedparser
import httpx

GOOGLE_NEWS_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

# Fallback feeds, used when Google News fails and as a pool of "new" topics for the explore slot.
# Articles that mention a reader topic are filed under it; the rest keep the feed's label.
FALLBACK_FEEDS = [
    ("https://feeds.bbci.co.uk/news/world/rss.xml", "World News"),
    ("https://feeds.bbci.co.uk/news/technology/rss.xml", "Technology"),
    ("https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "Science"),
    ("https://feeds.arstechnica.com/arstechnica/index", "Technology"),
    ("https://www.theverge.com/rss/index.xml", "Technology"),
]

MAX_AGE = timedelta(hours=48)
MAX_TEXT = 600
CACHE_TTL = 30 * 60
HEADLINE_SIMILARITY = 0.85
TIMEOUT = 8.0
USER_AGENT = "Mozilla/5.0 (compatible; Vale/0.2)"

_cache: dict[str, tuple[float, bytes]] = {}


# ---------- fetching ----------

def fetch_feed(url: str) -> bytes | None:
    """Fetch raw feed bytes, cached in memory for 30 minutes. Returns None on any failure."""
    hit = _cache.get(url)
    if hit and time.monotonic() - hit[0] < CACHE_TTL:
        return hit[1]
    try:
        response = httpx.get(url, timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    _cache[url] = (time.monotonic(), response.content)
    return response.content


def clear_cache() -> None:
    _cache.clear()


def google_news_url(topic: str) -> str:
    return GOOGLE_NEWS_URL.format(query=quote_plus(topic))


# ---------- parsing ----------

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def clean_text(raw: str) -> str:
    text = html.unescape(_TAG.sub(" ", raw or ""))
    return _SPACE.sub(" ", text).strip()


def article_id(url: str) -> str:
    return "a" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]


def _published(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def parse_feed(content: bytes, topic: str, default_source: str = "") -> list[dict]:
    """Turn RSS bytes into article dicts. Google News titles look like 'Headline - Source'."""
    feed = feedparser.parse(content)
    feed_source = default_source or clean_text(feed.feed.get("title", ""))
    articles = []
    for entry in feed.entries:
        url = entry.get("link", "").strip()
        title = clean_text(entry.get("title", ""))
        published = _published(entry)
        if not url or not title or not published:
            continue
        source = clean_text((entry.get("source") or {}).get("title", "")) or feed_source
        suffix = f" - {source}"
        if source and title.endswith(suffix):
            title = title[: -len(suffix)].strip()
        text = clean_text(entry.get("summary", ""))
        # Google News descriptions repeat the headline and source; keep only what adds information.
        if text.startswith(title):
            text = text[len(title):].strip()
        if source and text.endswith(source):
            text = text[: -len(source)].strip()
        articles.append(
            {
                "id": article_id(url),
                "topic": topic,
                "headline": title,
                "text": text[:MAX_TEXT],
                "source_name": source,
                "url": url,
                "published_at": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    return articles


# ---------- filtering ----------

def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def matches_topic(text: str, topic: str) -> bool:
    """True when every word of the topic appears in the text (case-insensitive, whole words)."""
    topic_words = _words(topic)
    return bool(topic_words) and topic_words <= _words(text)


def is_recent(article: dict, now: datetime) -> bool:
    published = datetime.strptime(article["published_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return now - MAX_AGE <= published <= now + timedelta(hours=1)


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def normalize_headline(headline: str) -> str:
    return " ".join(sorted(_words(headline)))


def _similar_normalized(matcher: SequenceMatcher, other: str) -> bool:
    """matcher holds one normalized headline as seq2; cheap upper bounds run before the full ratio."""
    matcher.set_seq1(other)
    return (
        matcher.real_quick_ratio() >= HEADLINE_SIMILARITY
        and matcher.quick_ratio() >= HEADLINE_SIMILARITY
        and matcher.ratio() >= HEADLINE_SIMILARITY
    )


def similar_headlines(a: str, b: str) -> bool:
    na, nb = normalize_headline(a), normalize_headline(b)
    if na == nb:
        return True
    matcher = SequenceMatcher(None, autojunk=False)
    matcher.set_seq2(nb)
    return _similar_normalized(matcher, na)


def dedupe(articles: list[dict]) -> list[dict]:
    """Drop repeats by URL and by near-identical headline, keeping the first one seen."""
    kept: list[dict] = []
    kept_norms: list[str] = []
    seen_urls: set[str] = set()
    seen_norms: set[str] = set()
    for article in articles:
        url = normalize_url(article["url"])
        if url in seen_urls:
            continue
        norm = normalize_headline(article["headline"])
        if norm in seen_norms:
            continue
        matcher = SequenceMatcher(None, autojunk=False)
        matcher.set_seq2(norm)
        if any(_similar_normalized(matcher, k) for k in kept_norms):
            continue
        seen_urls.add(url)
        seen_norms.add(norm)
        kept_norms.append(norm)
        kept.append(article)
    return kept


# ---------- gather ----------

def topics_to_query(topic_weights: dict[str, int]) -> list[str]:
    """Topics with weight above 0, strongest first. Blocked topics are never fetched."""
    return [t for t, w in sorted(topic_weights.items(), key=lambda kv: -kv[1]) if w > 0]


def gather(topic_weights: dict[str, int], now: datetime | None = None, fetch=fetch_feed) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    topics = topics_to_query(topic_weights)
    blocked = [t for t, w in topic_weights.items() if w < 0]

    # (feed url, topic label, is_fallback)
    jobs = [(google_news_url(t), t, False) for t in topics]
    jobs += [(url, label, True) for url, label in FALLBACK_FEEDS]
    with ThreadPoolExecutor(max_workers=8) as pool:
        contents = list(pool.map(lambda job: fetch(job[0]), jobs))

    articles: list[dict] = []
    for (_url, label, is_fallback), content in zip(jobs, contents):
        if not content:
            continue
        for article in parse_feed(content, label):
            haystack = f"{article['headline']} {article['text']}"
            if is_fallback:
                # File fallback stories under a reader topic when they clearly match one.
                article["topic"] = next((t for t in topics if matches_topic(haystack, t)), label)
            if any(matches_topic(haystack, b) for b in blocked):
                continue
            articles.append(article)

    return dedupe([a for a in articles if is_recent(a, now)])
