import json
from datetime import datetime, timezone

import pytest

from app import ai_editor, editions, gatherer, store

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
WEIGHTS = {"AI Agents": 10, "Cybersecurity": 8, "Science": 5}


def cand(i, topic, url=None):
    return {"id": f"h{i}", "topic": topic, "headline": f"{topic} story {i}", "text": f"Text {i}.",
            "source_name": f"Outlet {i}", "url": url or f"https://news.test/{topic}/{i}", "published_at": NOW}


@pytest.fixture
def edition(monkeypatch):
    """Today's edition built from fake news (no AI key -> fallback copy)."""
    store.update(lambda d: d["user"].update(onboarded=True, bio="CS student", topic_weights=WEIGHTS))
    topics = ["AI Agents", "Cybersecurity", "Science", "World News"]
    monkeypatch.setattr(gatherer, "gather", lambda w: [cand(i, topics[i % 4]) for i in range(16)])
    return editions.get_or_create_today()


@pytest.fixture
def climate_news(monkeypatch):
    calls = []

    def gather(weights):
        calls.append(weights)
        return [cand(100, "Climate Tech"), cand(101, "Climate Tech"), cand(102, "Other")]

    monkeypatch.setattr(gatherer, "gather", gather)
    return calls


def test_swap_replaces_exactly_one_article_and_keeps_the_rest(edition, climate_news):
    lead = edition["articles"][0]
    updated = editions.swap_story(edition["id"], lead["id"], "climate tech")

    before = {a["id"]: a for a in edition["articles"]}
    after = {a["id"]: a for a in updated["articles"]}
    assert list(after) == list(before)  # same ids, same order
    changed = [i for i in after if after[i] != before[i]]
    assert changed == [lead["id"]]

    new = after[lead["id"]]
    assert new["topic"] == "Climate Tech"
    assert new["is_lead"] is True  # swapping the lead keeps the lead slot
    assert new["swapped"] is True and new["skipped"] is False
    assert new["url"].startswith("https://news.test/Climate Tech/")
    assert "Climate Tech" in updated["sections"]
    # Only the requested topic is fetched.
    assert climate_news == [{"Climate Tech": 5}]
    # Saved to disk.
    assert store.load()["editions"][0]["articles"][0]["topic"] == "Climate Tech"


def test_swap_rewrites_takeaways_and_quiz_that_pointed_at_the_old_story(edition, climate_news):
    target = edition["three_takeaways"][0]["article_id"]
    updated = editions.swap_story(edition["id"], target, "Climate Tech")
    new = next(a for a in updated["articles"] if a["id"] == target)
    takeaway = next(t for t in updated["three_takeaways"] if t["article_id"] == target)
    assert takeaway["text"] == new["headline"]
    assert all(t["article_id"] in {a["id"] for a in updated["articles"]} for t in updated["three_takeaways"])
    assert target not in updated["connect_the_dots"]["article_ids"]


def test_swap_never_reuses_a_story_already_printed(edition, monkeypatch):
    printed = edition["articles"][3]["url"]
    monkeypatch.setattr(gatherer, "gather", lambda w: [cand(1, "AI Agents", url=printed), cand(2, "AI Agents")])
    updated = editions.swap_story(edition["id"], edition["articles"][1]["id"], "AI Agents")
    assert updated["articles"][1]["url"] == "https://news.test/AI Agents/2"


def test_swap_uses_one_ai_call_when_a_key_is_set(edition, climate_news, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = []

    def fake(prompt):
        calls.append(prompt)
        aid = edition["articles"][2]["id"]
        return json.dumps({
            "article": {"id": aid, "headline": "Solar startup raises funds", "summary": "Two sentences. Facts.",
                        "why_it_matters": "You asked for climate tech."},
            "takeaway": {"text": "A solar startup raised money.", "article_id": aid},
            "quiz": {"question": "What raised money?", "options": ["Solar", "Wind", "Coal"], "answer_index": 0,
                     "article_id": aid},
        })

    monkeypatch.setattr(ai_editor, "call_llm_story", fake)
    updated = editions.swap_story(edition["id"], edition["articles"][2]["id"], "Climate Tech")
    assert len(calls) == 1
    assert updated["articles"][2]["headline"] == "Solar startup raises funds"
    assert updated["articles"][2]["writer"] == "ai"


def test_swap_errors(edition, monkeypatch):
    with pytest.raises(editions.SwapError):
        editions.swap_story(edition["id"], "a99", "Space")
    with pytest.raises(editions.SwapError):
        editions.swap_story("ed-nope", "a1", "Space")
    monkeypatch.setattr(gatherer, "gather", lambda w: [])
    with pytest.raises(editions.GenerationError):
        editions.swap_story(edition["id"], "a1", "Basket Weaving")


def test_swap_api(client, edition, climate_news):
    response = client.post(f"/api/edition/{edition['id']}/swap", json={"article_id": "a1", "topic": "Climate Tech"})
    assert response.status_code == 200
    assert response.json()["articles"][0]["topic"] == "Climate Tech"
    assert client.post(f"/api/edition/{edition['id']}/swap", json={"article_id": "zz", "topic": "X"}).status_code == 404
    assert client.post(f"/api/edition/{edition['id']}/swap", json={"article_id": "a1", "topic": ""}).status_code == 422
