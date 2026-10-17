from datetime import date, datetime, timezone

import pytest

from app import editions, gatherer, learning, store

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
TODAY = date.today().isoformat()
TOPICS = ["AI Agents", "Cybersecurity", "Crypto", "Science"]


def cand(i, topic, batch="old"):
    return {"id": f"{batch}{i}", "topic": topic, "headline": f"{batch} {topic} headline {i}", "text": "",
            "source_name": f"{batch} outlet {i}", "url": f"https://news.test/{batch}/{i}", "published_at": NOW}


@pytest.fixture
def onboarded():
    store.update(lambda d: d["user"].update(
        onboarded=True, bio="", topic_weights={"AI Agents": 10, "Cybersecurity": 8, "Crypto": 6, "Science": 4},
    ))


@pytest.fixture
def news(monkeypatch):
    """The same 16 stories every time, plus 16 new ones from the second fetch on."""
    calls = []

    def gather(weights):
        calls.append(dict(weights))
        old = [cand(i, TOPICS[i % 4]) for i in range(16)]
        new = [cand(i, TOPICS[i % 4], "new") for i in range(16)] if len(calls) > 1 else []
        return old + new

    monkeypatch.setattr(gatherer, "gather", gather)
    return calls


def test_next_edition_increments_the_number_and_avoids_used_urls(onboarded, news):
    first = editions.get_or_create_today()
    second = editions.create_next()

    assert second["edition_number"] == first["edition_number"] + 1 == 2
    assert second["id"] == f"ed-{TODAY}-2"
    first_urls = {a["url"] for a in first["articles"]}
    assert not first_urls & {a["url"] for a in second["articles"]}
    # Today's edition is now the newest one.
    assert editions.get_or_create_today()["id"] == second["id"]


def test_next_edition_uses_the_updated_weights(onboarded, news):
    first = editions.get_or_create_today()
    crypto = [a for a in first["articles"] if a["topic"] == "Crypto"]
    assert len(crypto) >= 2
    data = store.load()
    for a in crypto[:2]:
        learning.apply_signal(data, "SKIP", first["id"], a["id"])
    store.save(data)

    editions.create_next()
    assert news[-1]["Crypto"] == 0  # 6 - 3 - 3: the next fetch sees the lower weight
    second = store.load()["editions"][-1]
    assert sum(a["topic"] == "Crypto" for a in second["articles"]) < len(crypto)


def test_list_is_newest_first(onboarded, news):
    first = editions.get_or_create_today()
    second = editions.create_next()
    rows = editions.list_editions(store.load())
    assert [r["id"] for r in rows] == [second["id"], first["id"]]
    assert rows[0]["edition_number"] == 2
    assert rows[1]["lead_headline"] == next(a["headline"] for a in first["articles"] if a["is_lead"])


def test_api_archive_round_trip(client, onboarded, news):
    first = client.get("/api/edition/today").json()
    second = client.post("/api/edition/next").json()
    assert second["edition_number"] == 2

    rows = client.get("/api/editions").json()
    assert [r["edition_number"] for r in rows] == [2, 1]
    assert client.get(f"/api/edition/{first['id']}").json()["id"] == first["id"]
    assert client.get("/api/edition/ed-nope").status_code == 404
    # "today" still works and is not swallowed by the {edition_id} route.
    assert client.get("/api/edition/today").json()["id"] == second["id"]


def test_api_next_requires_onboarding(client):
    assert client.post("/api/edition/next").status_code == 409
