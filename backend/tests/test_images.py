import json
import time
from io import BytesIO

import feedparser
import pytest
from PIL import Image as PILImage
from pypdf import PdfReader

from app import editions, gatherer, images, pdf, store

# Captured at import, before conftest swaps it out for each test.
REAL_FETCH_IMAGE = images.fetch_image

RSS = """<?xml version="1.0"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Feed</title>
  <item><title>Media content</title><link>https://a.test/1</link>
    <media:content url="https://cdn.test/small.jpg" medium="image" width="300"/>
    <media:content url="https://cdn.test/big.jpg" medium="image" width="1200"/></item>
  <item><title>BBC thumb</title><link>https://a.test/2</link>
    <media:thumbnail url="https://ichef.bbci.co.uk/ace/standard/240/cpsprodpb/abc/live/x.jpg" width="240"/></item>
  <item><title>Inline img</title><link>https://a.test/3</link>
    <description><![CDATA[<p><img src="https://cdn.test/inline.png" /> Text</p>]]></description></item>
  <item><title>Logo only</title><link>https://a.test/4</link>
    <media:thumbnail url="https://cdn.test/site-logo.png"/></item>
  <item><title>Bad scheme</title><link>https://a.test/5</link>
    <description><![CDATA[<img src="javascript:alert(1)">]]></description></item>
</channel></rss>"""


def png_bytes(w=400, h=300, color=(180, 60, 40)):
    out = BytesIO()
    PILImage.new("RGB", (w, h), color).save(out, "PNG")
    return out.getvalue()


# ---------- RSS images ----------

def test_rss_image_picks_the_best_safe_image():
    entries = feedparser.parse(RSS).entries
    assert images.rss_image(entries[0]) == "https://cdn.test/big.jpg"  # largest media:content
    assert images.rss_image(entries[1]) == "https://ichef.bbci.co.uk/ace/standard/800/cpsprodpb/abc/live/x.jpg"
    assert images.rss_image(entries[2]) == "https://cdn.test/inline.png"
    assert images.rss_image(entries[3]) is None  # logos are not news photos
    assert images.rss_image(entries[4]) is None  # only http(s)


def test_gatherer_keeps_the_rss_image():
    articles = gatherer.parse_feed(RSS.encode().replace(b"<title>Feed</title>", b"<title>Feed</title>").replace(b"</link>", b"</link><pubDate>Sat, 17 Oct 2026 08:00:00 GMT</pubDate>"), "Tech")
    assert articles[0]["image_url"] == "https://cdn.test/big.jpg"
    assert articles[4]["image_url"] is None


# ---------- og:image and Google News ----------

def test_og_image_reads_either_attribute_order_and_resolves_relative_urls(monkeypatch):
    pages = {
        "https://pub.test/a": '<head><meta property="og:image" content="/img/a.jpg"></head>',
        "https://pub.test/b": "<head><meta content='https://cdn.test/b.jpg' name='twitter:image'></head>",
        "https://pub.test/c": "<head><title>No image</title></head>",
    }
    monkeypatch.setattr(images, "fetch_text", lambda url, limit=0: (url, pages[url]))
    assert images.og_image("https://pub.test/a") == "https://pub.test/img/a.jpg"
    assert images.og_image("https://pub.test/b") == "https://cdn.test/b.jpg"
    assert images.og_image("https://pub.test/c") is None


GN = "https://news.google.com/rss/articles/CBMiABC123?oc=5"


def fake_google(monkeypatch, publisher="https://pub.test/story", og='<meta property="og:image" content="https://cdn.test/photo.jpg">'):
    calls = []

    def fetch_text(url, limit=0):
        calls.append(url)
        if "news.google.com" in url:
            return url, '<div jscontroller="x" data-n-a-sg="SIG" data-n-a-ts="1792200000"></div>'
        return url, f"<head>{og}</head>"

    def post_form(url, body):
        assert "CBMiABC123" in body and "SIG" in body and "1792200000" in body
        payload = json.dumps([["wrb.fr", "Fbv4je", json.dumps(["garturlres", publisher, 1])]])
        return ")]}'\n\n" + payload + "\n"

    monkeypatch.setattr(images, "fetch_text", fetch_text)
    monkeypatch.setattr(images, "post_form", post_form)
    return calls


def test_decodes_google_news_links_to_the_publisher(monkeypatch):
    fake_google(monkeypatch)
    assert images.is_google_news(GN)
    assert images.decode_google_news(GN) == "https://pub.test/story"


def test_find_for_google_news_story(monkeypatch):
    calls = fake_google(monkeypatch)
    found = images.find_for({"url": GN})
    assert found == {"publisher_url": "https://pub.test/story", "image_url": "https://cdn.test/photo.jpg"}
    images.find_for({"url": GN})
    assert len(calls) == 2  # second call came from the cache


def test_blocked_publishers_just_mean_no_photo(monkeypatch):
    def fetch_text(url, limit=0):
        raise RuntimeError("401 Unauthorized")

    monkeypatch.setattr(images, "fetch_text", fetch_text)
    assert images.find_for({"url": "https://reuters.test/story"}) == {}


def test_enrich_keeps_rss_images_and_respects_the_time_budget(monkeypatch):
    fake_google(monkeypatch)
    stories = [
        {"url": GN},
        {"url": "https://bbc.test/1", "image_url": "https://ichef.test/rss.jpg"},
    ]
    images.enrich(stories)
    assert stories[0]["image_url"] == "https://cdn.test/photo.jpg"
    assert stories[0]["publisher_url"] == "https://pub.test/story"
    assert stories[1]["image_url"] == "https://ichef.test/rss.jpg"

    def slow(article):
        time.sleep(2)
        return {"image_url": "https://late.test/x.jpg"}

    monkeypatch.setattr(images, "find_for", slow)
    late = [{"url": "https://slow.test/1"}]
    started = time.monotonic()
    images.enrich(late, budget=0.2)
    assert time.monotonic() - started < 1.5
    assert "image_url" not in late[0]


def test_to_jpeg_resizes_and_skips_icons():
    jpeg = images.to_jpeg(png_bytes(2000, 1000))
    assert PILImage.open(jpeg).size == (900, 450)
    assert images.to_jpeg(png_bytes(40, 40)) is None
    assert images.to_jpeg(b"not an image") is None


# ---------- editions and PDF ----------

def test_editions_store_photos_and_publisher_links(monkeypatch):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    store.update(lambda d: d["user"].update(onboarded=True, topic_weights={"AI": 10, "Space": 6}))
    monkeypatch.setattr(gatherer, "gather", lambda w: [
        {"id": f"h{i}", "topic": ["AI", "Space", "Other", "More"][i % 4], "headline": f"Story {i}", "text": "",
         "source_name": f"Outlet {i}", "url": f"https://news.test/{i}", "published_at": now, "image_url": None}
        for i in range(12)
    ])

    def enrich(articles, budget=0):
        for a in articles:
            a["image_url"] = f"https://cdn.test/{a['id']}.jpg"
            a["publisher_url"] = f"https://pub.test/{a['id']}"

    monkeypatch.setattr(images, "enrich", enrich)
    monkeypatch.setattr(images, "fetch_image", lambda url: png_bytes(color=(len(url) % 255, 80, 90)))
    edition = editions.get_or_create_today()
    lead = edition["articles"][0]
    assert lead["image_url"].startswith("/api/images/") and lead["image_kind"] == "news"
    assert lead["image_credit"] == f"Photo: {lead['source_name']}"
    assert lead["image_source_url"].startswith("https://cdn.test/")
    assert lead["publisher_url"].startswith("https://pub.test/")


def test_pdf_embeds_photos_with_credit_and_links_to_the_publisher():
    articles = [
        {"id": f"a{i}", "topic": "AI", "headline": f"Headline {i}", "summary": "Summary.", "why_it_matters": "",
         "source_name": f"Outlet {i}", "url": f"https://news.google.com/rss/articles/x{i}",
         "publisher_url": f"https://pub.test/{i}", "image_url": f"https://cdn.test/{i}.jpg",
         "image_credit": f"Photo: Outlet {i}",
         "is_lead": i == 1, "is_explore": False, "skipped": False}
        for i in range(1, 7)
    ]
    edition = {"id": "e", "edition_number": 3, "date": "2026-10-17", "reading_minutes": 3, "sections": ["AI"],
               "three_takeaways": [], "connect_the_dots": {}, "mind_vitamin": {}, "articles": articles}
    asked = []

    def fetch(url):
        asked.append(url)
        return png_bytes(color=(40 * len(asked), 90, 120))  # distinct, so the PDF can't merge them

    data = pdf.build_pdf(edition, "The Iqra Times", fetch_image=fetch)
    reader = PdfReader(BytesIO(data))
    photos_in_pdf = sum(len(page.images) for page in reader.pages)
    assert len(asked) == photos_in_pdf == 6  # every story, not just a few
    text = " ".join(" ".join(p.extract_text() for p in reader.pages).split())
    assert "Photo: Outlet 1" in text
    uris = [a.get_object()["/A"]["/URI"] for p in reader.pages for a in (p.get("/Annots") or []) if a.get_object().get("/A")]
    assert "https://pub.test/1" in uris
    assert not any("news.google.com" in u for u in uris)


def test_pdf_still_builds_when_photos_fail():
    edition = {"id": "e", "edition_number": 1, "date": "2026-10-17", "sections": [], "three_takeaways": [],
               "connect_the_dots": {}, "mind_vitamin": {},
               "articles": [{"id": "a1", "topic": "AI", "headline": "H", "summary": "S", "source_name": "X",
                             "url": "https://x.test", "image_url": "https://cdn.test/broken.jpg", "is_lead": True}]}
    data = pdf.build_pdf(edition, "T", fetch_image=lambda url: b"garbage")
    assert data.startswith(b"%PDF")



def test_pdf_photos_are_downloaded_once_then_cached(monkeypatch):
    downloads = []

    def download(url):
        downloads.append(url)
        return png_bytes()

    monkeypatch.setattr(images, "_download_image", download)
    images.clear_cache()
    assert REAL_FETCH_IMAGE("https://cdn.test/1.jpg") == REAL_FETCH_IMAGE("https://cdn.test/1.jpg")
    assert downloads == ["https://cdn.test/1.jpg"]


def test_wikimedia_downloads_identify_vale(monkeypatch):
    seen = {}

    class FakeStream:
        headers = {"content-type": "image/jpeg"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        def iter_bytes(self):
            yield b"jpegdata"

    class FakeClient:
        def __init__(self, headers=None, **kw):
            seen.setdefault("agents", []).append(headers["User-Agent"])

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url):
            return FakeStream()

    monkeypatch.setattr(images.httpx, "Client", FakeClient)
    images._download_image("https://thumb.wikimedia.org/wikipedia/commons/thumb/a/b.jpg")
    images._download_image("https://cdn.publisher.test/photo.jpg")
    assert seen["agents"][0].startswith("Vale/")
    assert seen["agents"][1].startswith("Mozilla/")


def test_resolve_links_decodes_only_the_chosen_google_stories(monkeypatch):
    asked = []

    def decode(url):
        asked.append(url)
        return "https://pub.test/" + url.rsplit("/", 1)[-1]

    monkeypatch.setattr(images, "decode_google_news", decode)
    stories = [
        {"url": "https://news.google.com/rss/articles/AAA"},
        {"url": "https://news.google.com/rss/articles/BBB", "publisher_url": "https://known.test/b"},
        {"url": "https://bbc.test/1"},
    ]
    images.resolve_links(stories)
    assert stories[0]["publisher_url"] == "https://pub.test/AAA"
    assert stories[1]["publisher_url"] == "https://known.test/b"
    assert "publisher_url" not in stories[2]
    assert asked == ["https://news.google.com/rss/articles/AAA"]
    # Decoded once: a second paper with the same story reuses it.
    again = [{"url": "https://news.google.com/rss/articles/AAA"}]
    images.resolve_links(again)
    assert again[0]["publisher_url"] == "https://pub.test/AAA" and len(asked) == 1


def test_resolve_links_respects_its_time_budget_and_survives_errors(monkeypatch):
    def decode(url):
        if url.endswith("boom"):
            raise RuntimeError("Google said no")
        time.sleep(2)
        return "https://late.test/x"

    monkeypatch.setattr(images, "decode_google_news", decode)
    stories = [{"url": "https://news.google.com/rss/articles/slow"}, {"url": "https://news.google.com/rss/articles/boom"}]
    started = time.monotonic()
    images.resolve_links(stories, budget=0.2)
    assert time.monotonic() - started < 1.5
    assert all("publisher_url" not in s for s in stories)


def test_a_link_decoded_during_a_timed_out_photo_lookup_is_kept(monkeypatch):
    monkeypatch.setattr(images, "decode_google_news", lambda url: "https://pub.test/kept")

    def og(url):
        raise RuntimeError("publisher too slow")

    monkeypatch.setattr(images, "og_image", og)
    images.find_for({"url": "https://news.google.com/rss/articles/KEEP"})
    monkeypatch.setattr(images, "decode_google_news", lambda url: None)  # Google now refuses
    story = {"url": "https://news.google.com/rss/articles/KEEP"}
    images.resolve_links([story])
    assert story["publisher_url"] == "https://pub.test/kept"
