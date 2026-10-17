from datetime import datetime, timezone

from app import gatherer, store

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fake_article(id, topic):
    return {
        "id": id, "topic": topic, "headline": f"Story {id}", "text": "",
        "source_name": "Wire", "url": f"https://news.test/{id}", "published_at": NOW,
    }


def test_debug_candidates_ranks_gathered_articles(client, monkeypatch):
    store.update(lambda d: d["user"].update(onboarded=True, topic_weights={"AI Agents": 10, "Crypto": -10}))
    seen = {}

    def fake_gather(weights):
        seen["weights"] = weights
        return [fake_article("a", "AI Agents"), fake_article("b", "World News")]

    monkeypatch.setattr(gatherer, "gather", fake_gather)
    body = client.get("/api/debug/candidates").json()

    assert seen["weights"] == {"AI Agents": 10, "Crypto": -10}
    assert body["topics_queried"] == ["AI Agents"]
    assert body["blocked_topics"] == ["Crypto"]
    assert body["candidate_count"] == 2
    assert body["paper"]["articles"][0]["id"] == "a"
    assert body["paper"]["articles"][0]["is_lead"] is True
    assert body["candidates"][0]["score"] == 13  # weight 10 + fresh bonus 3
