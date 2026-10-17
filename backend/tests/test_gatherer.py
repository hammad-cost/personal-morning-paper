from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from app import gatherer

FIXTURES = Path(__file__).parent / "fixtures"
GOOGLE = (FIXTURES / "google_news_ai_agents.xml").read_bytes()
BBC = (FIXTURES / "bbc_technology.xml").read_bytes()
NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
BBC_TECH = "https://feeds.bbci.co.uk/news/technology/rss.xml"


def make_fetch(feeds: dict):
    """Fake fetcher: returns fixture bytes for known URLs, None otherwise, and records calls."""
    calls = []

    def fetch(url):
        calls.append(url)
        return feeds.get(url)

    fetch.calls = calls
    return fetch


# ---------- parsing ----------

def test_parses_saved_google_news_rss():
    articles = gatherer.parse_feed(GOOGLE, "AI Agents")
    headlines = [a["headline"] for a in articles]
    # The undated item is dropped; " - Source" is stripped from titles.
    assert len(articles) == 4
    assert headlines[0] == "Rogue AI agents broke into firms’ live systems, government says"
    assert headlines[1] == "Open-source AI agent framework hits 1.0 & adds memory"
    first = articles[0]
    assert first["source_name"] == "Reuters"
    assert first["topic"] == "AI Agents"
    assert first["url"] == "https://news.google.com/rss/articles/rogue-agents-reuters?oc=5"
    assert first["published_at"] == "2026-10-17T06:00:00Z"
    assert first["id"] == gatherer.article_id(first["url"])
    # Google's description only repeats headline + source, so no extra text is kept.
    assert first["text"] == ""


def test_parses_bbc_rss_with_description_text():
    articles = gatherer.parse_feed(BBC, "Technology")
    assert articles[0]["source_name"] == "BBC News"
    assert articles[0]["text"].startswith("Researchers say the chip")
    assert all(len(a["text"]) <= gatherer.MAX_TEXT for a in articles)


def test_clean_text_strips_html_and_entities():
    assert gatherer.clean_text("<b>Hello</b>&nbsp;&amp; <i>world</i>") == "Hello & world"


# ---------- dedupe ----------

def article(url, headline, **extra):
    return {"id": gatherer.article_id(url), "url": url, "headline": headline, **extra}


def test_dedupe_removes_same_url():
    items = [
        article("https://example.com/story", "First headline"),
        article("https://EXAMPLE.com/story/#comments", "Totally different words here"),
    ]
    assert [a["headline"] for a in gatherer.dedupe(items)] == ["First headline"]


def test_dedupe_removes_near_same_headline():
    items = [
        article("https://a.com/1", "Rogue AI agents broke into firms’ live systems, government says"),
        article("https://b.com/2", "Rogue AI Agents Broke Into Firms' Live Systems, Government Says!"),
        article("https://c.com/3", "Rogue AI agent broke into firm live systems, government says"),
        article("https://d.com/4", "Quantum chip sets new error-correction record"),
    ]
    kept = gatherer.dedupe(items)
    assert [a["url"] for a in kept] == ["https://a.com/1", "https://d.com/4"]


def test_similar_headlines_keeps_different_stories():
    assert not gatherer.similar_headlines("AI agents book holidays", "Quantum chip sets record")


def test_matches_topic_needs_every_word():
    assert gatherer.matches_topic("AI agents can now book your holiday", "AI Agents")
    assert not gatherer.matches_topic("Agents of change", "AI Agents")
    assert not gatherer.matches_topic("Mail delivery", "AI")  # whole words only


# ---------- gather ----------

WEIGHTS = {"AI Agents": 10, "Cybersecurity": 10, "Space": 0, "Celebrity Gossip": -10}


def test_blocked_and_zero_weight_topics_are_never_queried():
    fetch = make_fetch({})
    gatherer.gather(WEIGHTS, now=NOW, fetch=fetch)
    queried = [u for u in fetch.calls if u.startswith("https://news.google.com")]
    assert queried == [gatherer.google_news_url("AI Agents"), gatherer.google_news_url("Cybersecurity")]
    assert not any("Celebrity" in u or "Space" in u for u in fetch.calls)
    assert gatherer.topics_to_query(WEIGHTS) == ["AI Agents", "Cybersecurity"]


def test_gather_filters_dedupes_and_files_fallback_stories():
    fetch = make_fetch({gatherer.google_news_url("AI Agents"): GOOGLE, BBC_TECH: BBC})
    articles = gatherer.gather(WEIGHTS, now=NOW, fetch=fetch)
    by_headline = {a["headline"]: a for a in articles}

    # 48-hour filter and near-duplicate removal.
    assert "Last week's AI agent roundup" not in by_headline
    assert not any(h.startswith("Rogue AI Agents Broke") for h in by_headline)
    # Fallback story mentioning a reader topic is filed under it; others keep the feed label.
    assert by_headline["AI agents can now book your holiday, airline says"]["topic"] == "AI Agents"
    assert by_headline["Quantum chip sets new error-correction record"]["topic"] == "Technology"
    # Stories matching a blocked topic are dropped.
    assert "Celebrity gossip site fined over fake stories" not in by_headline
    assert len(articles) == 4


def test_gather_survives_google_news_failing():
    fetch = make_fetch({BBC_TECH: BBC})  # every Google query returns None
    articles = gatherer.gather(WEIGHTS, now=NOW, fetch=fetch)
    assert {a["source_name"] for a in articles} == {"BBC News"}
    assert len(articles) == 2


# ---------- fetching ----------

@pytest.fixture
def fake_httpx(monkeypatch):
    gatherer.clear_cache()
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if "fail" in url:
            raise httpx.ConnectError("offline")
        return httpx.Response(200, content=b"<rss/>", request=httpx.Request("GET", url))

    monkeypatch.setattr(gatherer.httpx, "get", fake_get)
    yield calls
    gatherer.clear_cache()


def test_fetch_feed_caches_for_30_minutes(fake_httpx, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(gatherer.time, "monotonic", lambda: clock[0])
    assert gatherer.fetch_feed("https://feed.test/rss") == b"<rss/>"
    clock[0] += 29 * 60
    gatherer.fetch_feed("https://feed.test/rss")
    assert len(fake_httpx) == 1
    clock[0] += 2 * 60
    gatherer.fetch_feed("https://feed.test/rss")
    assert len(fake_httpx) == 2


def test_fetch_feed_returns_none_on_network_error(fake_httpx):
    assert gatherer.fetch_feed("https://fail.test/rss") is None
