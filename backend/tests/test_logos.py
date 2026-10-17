"""Publisher logos for the feed's profile pictures."""
from io import BytesIO

from PIL import Image

from app import editions, gatherer, logos, store


def png(size, color=(200, 30, 30)):
    out = BytesIO()
    Image.new("RGB", (size, size), color).save(out, "PNG")
    return out.getvalue()


def test_source_domain_prefers_the_feed_source_then_the_publisher_link():
    assert logos.source_domain({"source_url": "https://www.reuters.com", "url": "https://news.google.com/rss/articles/x"}) == "reuters.com"
    assert logos.source_domain({"publisher_url": "https://nltimes.nl/2026/10/17/a", "url": "https://news.google.com/rss/articles/x"}) == "nltimes.nl"
    assert logos.source_domain({"url": "https://news.google.com/rss/articles/x"}) is None
    assert logos.source_domain({"url": "https://www.bbc.co.uk/news/1"}) == "bbc.co.uk"


def test_gatherer_keeps_the_google_news_source_site():
    rss = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
    <item><title>Agents ship - Reuters</title><link>https://news.google.com/rss/articles/abc</link>
    <pubDate>Fri, 16 Oct 2026 09:00:00 GMT</pubDate><source url="https://www.reuters.com">Reuters</source></item>
    </channel></rss>"""
    [a] = gatherer.parse_feed(rss, "AI")
    assert a["source_name"] == "Reuters" and a["source_url"] == "https://www.reuters.com"


def test_picks_the_sharpest_logo_and_caches_it_on_disk(monkeypatch, client):
    asked = []

    def fetch(url):
        asked.append(url)
        return png(16) if "google" in url else png(64)  # Google only has a tiny one here

    monkeypatch.setattr(logos, "fetch", fetch)
    r = client.get("/api/logos/arabnews.com")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert Image.open(BytesIO(r.content)).size == (64, 64)
    assert len(asked) == 2
    assert (logos.logos_dir() / "arabnews.com.png").is_file()
    logos.clear_cache()
    assert client.get("/api/logos/arabnews.com").status_code == 200
    assert len(asked) == 2  # served from disk


def test_stops_at_a_good_google_logo(monkeypatch):
    asked = []
    monkeypatch.setattr(logos, "fetch", lambda url: asked.append(url) or png(128))
    assert logos.get("reuters.com")
    assert len(asked) == 1


def test_unknown_sites_and_bad_domains_get_404_without_fetching_them(monkeypatch, client):
    asked = []
    monkeypatch.setattr(logos, "fetch", lambda url: asked.append(url) or None)
    assert client.get("/api/logos/no-such-site.com").status_code == 404
    assert client.get("/api/logos/no-such-site.com").status_code == 404
    assert len(asked) == 2  # both services once; the "no logo" answer is remembered
    for bad in ["localhost", "127.0.0.1", "evil.com%2F..%2Fx", "a..b.com"]:
        assert client.get(f"/api/logos/{bad}").status_code == 404
    assert all(u.startswith(("https://www.google.com/", "https://icons.duckduckgo.com/")) for u in asked)


def test_new_editions_record_each_story_publisher_domain(monkeypatch):
    import time
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    store.update(lambda d: d["user"].update(onboarded=True, topic_weights={"AI": 10}))
    monkeypatch.setattr(gatherer, "gather", lambda w: [
        {"id": f"h{i}", "topic": "AI", "headline": f"Story {i}", "text": "", "source_name": f"Outlet {i}",
         "source_url": f"https://www.outlet{i}.com", "url": f"https://news.google.com/rss/articles/{i}",
         "published_at": now, "image_url": None}
        for i in range(6)
    ])
    edition = editions.get_or_create_today()
    assert all(a["source_domain"] == f"outlet{a['source_name'].split()[-1]}.com" for a in edition["articles"])
