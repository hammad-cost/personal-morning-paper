import time
from io import BytesIO

from PIL import Image as PILImage
from pypdf import PdfReader

from app import editions, gatherer, images, pdf, photos, ranker, store


def png_bytes(color=(120, 60, 40), w=640, h=400):
    out = BytesIO()
    PILImage.new("RGB", (w, h), color).save(out, "PNG")
    return out.getvalue()


def wiki(results):
    """Fake wiki_search: query -> list of hits."""
    return lambda query, limit: results.get(query, [])


COMMONS = "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/"


# ---------- matching rules ----------

def test_subject_titles_must_be_the_subject():
    assert photos.title_matches("Palo Alto Networks", "Palo Alto Networks", strict=True)
    assert photos.title_matches("Starship (spacecraft)", "Starship", strict=True)
    assert not photos.title_matches("Albert Heijn Jr.", "Albert Heijn", strict=True)
    assert not photos.title_matches("SpaceXAI", "SpaceX", strict=True)
    # Real mismatches seen live: a different person, a king for a market story, a list page.
    assert not photos.title_matches("Gerrit Jan Heijn", "Albert Heijn", strict=True)
    assert not photos.title_matches("Salman of Saudi Arabia", "Saudi Arabia", strict=True)
    assert not photos.title_matches("List of government space agencies", "Space agencies", strict=True)
    assert not photos.title_matches("Lego Mindstorms", "Kondo WhatsApp MCP", strict=True)


def test_topic_titles_need_every_topic_word():
    assert photos.title_matches("Intelligent agent", "AI Agents")  # plural/stem, short words ignored
    assert photos.title_matches("Rover (space exploration)", "Space exploration")
    assert photos.title_matches("Climate technology", "Climate Tech")  # tech ~ technology
    assert not photos.title_matches("Clean technology", "Climate Tech")
    assert not photos.title_matches("Vinod Khosla", "Climate Tech")


def test_subject_photo_skips_logos_non_free_files_and_loose_matches(monkeypatch):
    monkeypatch.setattr(photos, "wiki_search", wiki({
        "Albert Heijn": [
            {"title": "Albert Heijn", "url": COMMONS + "Albert_Heijn_Logo.svg/960px-Albert_Heijn_Logo.svg.png"},
            {"title": "Albert Heijn", "url": "https://upload.wikimedia.org/wikipedia/en/a/aa/Store.jpg"},  # non-free (en)
            {"title": "Albert Heijn", "url": COMMONS + "Albert_Heijn_store.jpg/960px-Albert_Heijn_store.jpg"},
        ],
        "HackerOne": [{"title": "Mårten Mickos", "url": COMMONS + "Marten.jpg/960px-Marten.jpg"}],
    }))
    assert photos.subject_photo("Albert Heijn")["url"].endswith("Albert_Heijn_store.jpg")
    assert photos.subject_photo("HackerOne") is None  # the CEO's portrait is not a photo of the company
    assert photos.subject_photo("") is None


def test_topic_photos_keep_only_matching_pages(monkeypatch):
    monkeypatch.setattr(photos, "wiki_search", wiki({"Climate Tech": [
        {"title": "Vinod Khosla", "url": COMMONS + "Khosla.jpg/960px-Khosla.jpg"},
        {"title": "Clean technology", "url": COMMONS + "Solar.jpg/960px-Solar.jpg"},  # missing "climate"
        {"title": "Climate technology", "url": COMMONS + "Wind.jpg/960px-Wind.jpg"},
    ]}))
    titles = [h["title"] for h in photos.topic_photos("Climate Tech")]
    assert "Vinod Khosla" not in titles
    assert "Climate technology" in titles


# ---------- the chain: every story always ends up with a picture ----------

def story(i, topic="Cybersecurity", image_url=None):
    return {"id": f"a{i}", "topic": topic, "source_name": f"Outlet {i}", "image_url": image_url}


def test_layer_1_news_photo_is_stored_and_served(client, monkeypatch):
    monkeypatch.setattr(images, "fetch_image", lambda url: png_bytes())
    articles = [story(1, image_url="https://cdn.test/news.jpg")]
    photos.ensure(articles)
    a = articles[0]
    assert a["image_kind"] == "news" and a["image_credit"] == "Photo: Outlet 1"
    assert a["image_url"].startswith("/api/images/")
    served = client.get(a["image_url"])
    assert served.status_code == 200 and served.headers["content-type"] == "image/jpeg"
    assert PILImage.open(BytesIO(served.content)).format == "JPEG"


def test_layer_2_subject_photo_when_the_news_photo_fails(monkeypatch):
    monkeypatch.setattr(images, "fetch_image", lambda url: None if "blocked" in url else png_bytes())
    monkeypatch.setattr(photos, "wiki_search", wiki({"Palo Alto Networks": [
        {"title": "Palo Alto Networks", "url": COMMONS + "PAN_HQ.jpg/960px-PAN_HQ.jpg"}]}))
    articles = [story(1, image_url="https://blocked.test/reuters.jpg")]
    photos.ensure(articles, {"a1": "Palo Alto Networks"})
    assert articles[0]["image_kind"] == "subject"
    assert articles[0]["image_credit"] == "Photo: Wikimedia Commons · Palo Alto Networks"


def test_layer_3_topic_photos_rotate_within_a_section(monkeypatch):
    monkeypatch.setattr(images, "fetch_image", lambda url: png_bytes(color=(len(url) % 250, 10, 10)))
    monkeypatch.setattr(photos, "wiki_search", wiki({"Space exploration": [
        {"title": "Space exploration", "url": COMMONS + "One.jpg/960px-One.jpg"},
        {"title": "Rover (space exploration)", "url": COMMONS + "Rover.jpg/960px-Rover.jpg"},
    ]}))
    articles = [story(1, "Space exploration"), story(2, "Space exploration")]
    photos.ensure(articles)
    assert [a["image_kind"] for a in articles] == ["topic", "topic"]
    assert articles[0]["image_url"] != articles[1]["image_url"]  # not the same picture twice
    assert articles[1]["image_credit"] == "Topic photo: Wikimedia Commons · Rover (space exploration)"


def test_ai_hint_finds_better_topic_photos_first(monkeypatch):
    monkeypatch.setattr(photos, "wiki_search", wiki({
        "Spaceflight": [{"title": "Spaceflight", "url": COMMONS + "Launch.jpg/960px-Launch.jpg"}],
        "Space": [
            {"title": "Liminal space", "url": COMMONS + "Hall.jpg/960px-Hall.jpg"},
            {"title": "Outer space", "url": COMMONS + "Earth.jpg/960px-Earth.jpg"},
        ],
    }))
    titles = [h["title"] for h in photos.topic_photos("Space", "Spaceflight")]
    assert titles[0] == "Spaceflight"  # the AI's pick comes first
    assert "Outer space" in titles  # the section name still adds more photos


def test_topic_photos_go_only_to_stories_that_need_them(monkeypatch):
    monkeypatch.setattr(images, "fetch_image", lambda url: png_bytes(color=(len(url) % 250, 20, 20)))
    monkeypatch.setattr(photos, "wiki_search", wiki({
        "Cybersecurity": [
            {"title": "Capture the flag (cybersecurity)", "url": COMMONS + "CTF.jpg/960px-CTF.jpg"},
            {"title": "European Cybersecurity Challenge", "url": COMMONS + "ECSC.jpg/960px-ECSC.jpg"},
        ],
        "Palo Alto Networks": [{"title": "Palo Alto Networks", "url": COMMONS + "PAN.jpg/960px-PAN.jpg"}],
    }))
    articles = [story(1), story(2), story(3)]  # all Cybersecurity; story 2 has its own subject photo
    photos.ensure(articles, {"a2": "Palo Alto Networks"})
    assert [a["image_kind"] for a in articles] == ["topic", "subject", "topic"]
    assert len({a["image_url"] for a in articles}) == 3  # nobody repeats a picture


def test_layer_4_vale_illustration_when_the_internet_is_gone():
    # conftest blocks every network call, so only the local illustration can work.
    articles = [story(1, "Quantum Computing", image_url="https://cdn.test/x.jpg"), story(2, "Quantum Computing")]
    photos.ensure(articles, {"a1": "IBM"})
    for a in articles:
        assert a["image_kind"] == "illustration"
        assert a["image_credit"] == "Vale illustration · Quantum Computing"
        path = photos.local_name(a["image_url"].split("/")[-1])
        assert path and PILImage.open(path).size == (1200, 675)


def test_served_names_are_validated(client):
    assert client.get("/api/images/..%2Fstore.json").status_code == 404
    assert client.get("/api/images/missing.jpg").status_code == 404
    assert photos.local_name("../store.json") is None


def test_every_story_in_a_new_edition_has_a_picture_even_offline(monkeypatch):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    store.update(lambda d: d["user"].update(onboarded=True, topic_weights={"AI": 10, "Space": 6}))
    monkeypatch.setattr(gatherer, "gather", lambda w: [
        {"id": f"h{i}", "topic": ["AI", "Space", "Other", "More"][i % 4], "headline": f"Story {i}", "text": "",
         "source_name": f"Outlet {i}", "url": f"https://news.test/{i}", "published_at": now, "image_url": None}
        for i in range(12)
    ])
    edition = editions.get_or_create_today()
    assert len(edition["articles"]) == 12  # every fake story fits in a 20-story paper
    assert all(a["image_url"].startswith("/api/images/") and a["image_credit"] for a in edition["articles"])


def test_old_editions_get_pictures_when_opened(client):
    old = {"id": "ed-old", "edition_number": 1, "date": "2026-10-16", "sections": ["AI"], "articles": [
        {"id": "a1", "topic": "AI", "headline": "H", "summary": "S", "source_name": "X", "url": "https://x.test",
         "is_lead": True, "skipped": False}]}
    store.update(lambda d: d["editions"].append(old))
    body = client.get("/api/edition/ed-old").json()
    assert body["articles"][0]["image_url"].startswith("/api/images/")
    assert store.load()["editions"][0]["articles"][0]["image_kind"] == "illustration"  # saved, not redone each time


def test_pdf_reads_stored_pictures_from_disk_for_every_story():
    articles = [story(i, "AI") for i in range(1, 5)]
    photos.ensure(articles)  # offline -> illustrations stored locally
    for i, a in enumerate(articles, start=1):
        a.update(headline=f"Headline {i}", summary="S", url=f"https://x.test/{i}", is_lead=i == 1, skipped=False)
    edition = {"id": "e", "edition_number": 1, "date": "2026-10-17", "sections": ["AI"], "three_takeaways": [],
               "connect_the_dots": {}, "mind_vitamin": {}, "articles": articles}

    def no_network(url):
        raise AssertionError("PDF should read stored pictures from disk")

    data = pdf.build_pdf(edition, "T", fetch_image=no_network)
    assert sum(len(p.images) for p in PdfReader(BytesIO(data)).pages) >= 1
    assert "Vale illustration" in " ".join(PdfReader(BytesIO(data)).pages[0].extract_text().split())


# ---------- ranker tie-break ----------

def art(id, score_hours, image=None):
    return {"id": id, "topic": "AI", "headline": id, "text": "", "source_name": f"S{id}", "url": f"https://n.test/{id}",
            "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - score_hours * 3600)),
            "image_url": image}


def test_near_ties_go_to_stories_with_a_real_photo():
    # Same score (both under 12h): the one with a photo leads.
    paper = ranker.rank([art("plain", 1), art("photo", 2, "https://cdn.test/p.jpg")], {"AI": 10})
    assert paper["articles"][0]["id"] == "photo"
    # A clearly higher score still wins without a photo (3 points of freshness).
    paper = ranker.rank([art("fresh", 1), art("old-photo", 30, "https://cdn.test/p.jpg")], {"AI": 10})
    assert paper["articles"][0]["id"] == "fresh"
    assert paper["articles"][0]["score"] == 13  # the shown score is unchanged
