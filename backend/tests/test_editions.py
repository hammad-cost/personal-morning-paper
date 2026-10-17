import threading
from datetime import date, datetime, timezone

import pytest

from app import editions, gatherer, store

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
TODAY = date.today().isoformat()
WEIGHTS = {"AI Agents": 10, "Cybersecurity": 8, "Celebrity Gossip": -10}


def candidates(n=16):
    topics = ["AI Agents", "Cybersecurity", "World News", "Science"]
    return [
        {"id": f"h{i}", "topic": topics[i % len(topics)], "headline": f"Story number {i}", "text": f"Some text {i}.",
         "source_name": f"Outlet {i}", "url": f"https://news.test/{i}", "published_at": NOW}
        for i in range(n)
    ]


@pytest.fixture
def onboarded():
    store.update(lambda d: d["user"].update(onboarded=True, name="Ayesha", bio="CS student", topic_weights=WEIGHTS))


@pytest.fixture
def fake_gather(monkeypatch):
    calls = []

    def gather(weights):
        calls.append(weights)
        return candidates()

    monkeypatch.setattr(gatherer, "gather", gather)
    return calls


def test_builds_and_saves_todays_edition(onboarded, fake_gather):
    edition = editions.get_or_create_today()
    assert edition["id"] == f"ed-{TODAY}-1"
    assert edition["edition_number"] == 1
    assert edition["date"] == TODAY
    assert edition["writer"] == "fallback"  # no key in tests
    assert len(edition["articles"]) == 10
    assert [a["id"] for a in edition["articles"]] == [f"a{i}" for i in range(1, 11)]
    assert edition["articles"][0]["is_lead"] is True
    assert all(a["skipped"] is False and a["clicked"] is False for a in edition["articles"])
    assert edition["sections"][:2] == ["AI Agents", "Cybersecurity"]
    assert edition["reading_minutes"] >= 1
    assert store.load()["editions"] == [edition]


def test_every_takeaway_and_quiz_question_references_a_real_article(onboarded, fake_gather):
    edition = editions.get_or_create_today()
    ids = {a["id"] for a in edition["articles"]}
    assert len(edition["three_takeaways"]) == 3
    assert {t["article_id"] for t in edition["three_takeaways"]} <= ids
    assert {q["article_id"] for q in edition["recall_quiz"]} <= ids
    assert set(edition["connect_the_dots"]["article_ids"]) <= ids


def test_today_twice_does_not_create_a_second_edition(onboarded, fake_gather):
    first = editions.get_or_create_today()
    second = editions.get_or_create_today()
    assert first["id"] == second["id"]
    assert len(store.load()["editions"]) == 1
    assert len(fake_gather) == 1


def test_concurrent_requests_create_one_edition(onboarded, monkeypatch):
    started = threading.Event()

    def slow_gather(weights):
        started.set()
        threading.Event().wait(0.2)
        return candidates()

    monkeypatch.setattr(gatherer, "gather", slow_gather)
    results = []
    threads = [threading.Thread(target=lambda: results.append(editions.get_or_create_today())) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len({r["id"] for r in results}) == 1
    assert len(store.load()["editions"]) == 1


def test_status_walks_through_the_printing_press_steps(onboarded, monkeypatch):
    seen = []
    real_set = editions._set_status

    def spy(**changes):
        real_set(**changes)
        seen.append(editions.get_status()["step"])

    monkeypatch.setattr(editions, "_set_status", spy)
    monkeypatch.setattr(gatherer, "gather", lambda w: candidates())
    edition = editions.get_or_create_today()

    assert [s for s in dict.fromkeys(seen) if s] == ["gathering", "choosing", "writing", "setting"]
    status = editions.get_status()
    assert status["state"] == "done"
    assert status["edition_id"] == edition["id"]


def test_not_enough_news_is_a_clear_error(onboarded, monkeypatch):
    monkeypatch.setattr(gatherer, "gather", lambda w: candidates(2))
    with pytest.raises(editions.GenerationError):
        editions.get_or_create_today()
    assert editions.get_status()["state"] == "error"
    assert store.load()["editions"] == []


def test_reading_minutes_from_word_count():
    words = " ".join(["word"] * 450)
    edition = {
        "connect_the_dots": {"text": ""}, "mind_vitamin": {"content": ""}, "three_takeaways": [],
        "articles": [{"headline": "", "summary": words, "why_it_matters": ""}],
    }
    assert editions.reading_minutes(edition) == 3


# ---------- API ----------

def test_api_today_generates_once_and_state_reports_it(client, onboarded, fake_gather):
    assert client.get("/api/state").json()["today_edition_id"] is None
    first = client.get("/api/edition/today")
    assert first.status_code == 200
    assert client.get("/api/edition/today").json()["id"] == first.json()["id"]
    assert client.get("/api/state").json()["today_edition_id"] == first.json()["id"]
    assert client.get("/api/generation/status").json()["state"] == "done"


def test_api_today_requires_onboarding(client):
    assert client.get("/api/edition/today").status_code == 409


def test_api_today_returns_503_when_no_news(client, onboarded, monkeypatch):
    monkeypatch.setattr(gatherer, "gather", lambda w: [])
    response = client.get("/api/edition/today")
    assert response.status_code == 503
    assert "Not enough fresh news" in response.json()["detail"]
