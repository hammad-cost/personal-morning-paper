from datetime import date

from app import store

PROFILE = {
    "name": "Ayesha",
    "bio": "CS student into AI agents and cybersecurity",
    "topic_weights": {"AI Agents": 10, "Cybersecurity": 10, "Celebrity Gossip": -10},
}


def test_state_starts_not_onboarded(client):
    body = client.get("/api/state").json()
    assert body["onboarded"] is False
    assert body["today_edition_id"] is None
    assert body["profile"]["name"] == ""


def test_onboard_sets_onboarded_true(client):
    response = client.post("/api/onboard", json=PROFILE)
    assert response.status_code == 200
    body = response.json()
    assert body["onboarded"] is True
    assert body["profile"]["paper_title"] == "THE AYESHA CHRONICLE"
    assert body["profile"]["topic_weights"]["Celebrity Gossip"] == -10
    assert body["profile"]["created_at"]

    saved = store.load()["user"]
    assert saved["onboarded"] is True
    assert saved["name"] == "Ayesha"
    assert client.get("/api/state").json()["onboarded"] is True


def test_onboard_keeps_custom_paper_title(client):
    body = client.post("/api/onboard", json={**PROFILE, "paper_title": "The Daily Ayesha"}).json()
    assert body["profile"]["paper_title"] == "The Daily Ayesha"


def test_onboard_rejects_blank_name(client):
    assert client.post("/api/onboard", json={**PROFILE, "name": "   "}).status_code == 422


def test_reset_clears_profile(client):
    client.post("/api/onboard", json=PROFILE)
    body = client.post("/api/reset").json()
    assert body["onboarded"] is False
    assert store.load() == store.defaults()


def test_state_reports_today_edition_id(client):
    today = date.today().isoformat()
    store.update(lambda d: d["editions"].extend([
        {"id": "ed-old", "date": "2000-01-01"},
        {"id": f"ed-{today}-1", "date": today},
    ]))
    assert client.get("/api/state").json()["today_edition_id"] == f"ed-{today}-1"
