import pytest

from app import learning, store

EDITION_ID = "ed-2026-10-17-1"


def make_data(weights=None):
    data = store.defaults()
    data["user"].update(onboarded=True, topic_weights=weights or {"Crypto": 5, "AI Agents": 10})
    data["editions"].append({
        "id": EDITION_ID,
        "articles": [
            {"id": "a1", "topic": "Crypto", "headline": "Bitcoin wobbles", "source_name": "TechCrunch",
             "skipped": False, "clicked": False},
            {"id": "a2", "topic": "AI Agents", "headline": "Agents book trips", "source_name": "Reuters",
             "skipped": False, "clicked": False},
        ],
    })
    return data


def article(data, aid):
    return next(a for a in data["editions"][0]["articles"] if a["id"] == aid)


def test_skip_lowers_topic_by_3_and_marks_the_story_skipped():
    data = make_data()
    sig = learning.apply_signal(data, "SKIP", EDITION_ID, "a1")
    assert data["user"]["topic_weights"]["Crypto"] == 2
    assert sig["delta"] == -3 and sig["topic"] == "Crypto"
    assert article(data, "a1")["skipped"] is True
    assert data["signals"] == [sig]


def test_undo_skip_adds_3_back_and_unskips():
    data = make_data()
    learning.apply_signal(data, "SKIP", EDITION_ID, "a1")
    learning.apply_signal(data, "UNSKIP", EDITION_ID, "a1")
    assert data["user"]["topic_weights"]["Crypto"] == 5
    assert article(data, "a1")["skipped"] is False


def test_click_adds_2_to_topic_and_1_to_source():
    data = make_data()
    sig = learning.apply_signal(data, "CLICK", EDITION_ID, "a2")
    assert data["user"]["topic_weights"]["AI Agents"] == 12
    assert data["user"]["source_weights"] == {"Reuters": 1}
    assert sig["source_delta"] == 1
    assert article(data, "a2")["clicked"] is True


def test_repeats_and_stale_undos_change_nothing():
    data = make_data()
    learning.apply_signal(data, "CLICK", EDITION_ID, "a2")
    assert learning.apply_signal(data, "CLICK", EDITION_ID, "a2") is None
    assert learning.apply_signal(data, "UNSKIP", EDITION_ID, "a1") is None
    learning.apply_signal(data, "SKIP", EDITION_ID, "a1")
    assert learning.apply_signal(data, "SKIP", EDITION_ID, "a1") is None
    assert data["user"]["topic_weights"] == {"Crypto": 2, "AI Agents": 12}
    assert len(data["signals"]) == 2


def test_weights_clamp_at_minus_15_and_25():
    data = make_data({"Crypto": -14, "AI Agents": 24})
    sig = learning.apply_signal(data, "SKIP", EDITION_ID, "a1")
    assert data["user"]["topic_weights"]["Crypto"] == -15
    assert sig["delta"] == -1  # only the change that actually happened is logged
    learning.apply_signal(data, "CLICK", EDITION_ID, "a2")
    assert data["user"]["topic_weights"]["AI Agents"] == 25
    assert learning.clamp(-99) == -15 and learning.clamp(99) == 25


def test_quiz_signals():
    data = make_data()
    learning.apply_signal(data, "QUIZ_RIGHT", EDITION_ID, "a2")
    assert data["user"]["topic_weights"]["AI Agents"] == 11
    sig = learning.apply_signal(data, "QUIZ_WRONG", EDITION_ID, "a2")
    assert sig["delta"] == 0
    assert data["user"]["topic_weights"]["AI Agents"] == 11


def test_copilot_moves_a_topic_by_5_and_can_add_a_new_one():
    data = make_data()
    learning.apply_signal(data, "COPILOT", topic="crypto", delta=-5, note="less crypto please")
    learning.apply_signal(data, "COPILOT", topic="Quantum Computing", delta=5, note="more quantum")
    assert data["user"]["topic_weights"] == {"Crypto": 0, "AI Agents": 10, "Quantum Computing": 5}
    assert data["signals"][-1]["note"] == "more quantum"


@pytest.mark.parametrize("kwargs", [
    {"action": "LIKE"},
    {"action": "SKIP"},  # no article
    {"action": "COPILOT", "topic": "Crypto", "delta": 3},
    {"action": "COPILOT", "delta": 5},
])
def test_bad_signals_are_rejected(kwargs):
    with pytest.raises(learning.SignalError):
        learning.apply_signal(make_data(), **kwargs)


def test_unknown_article_is_not_found():
    with pytest.raises(learning.NotFound):
        learning.apply_signal(make_data(), "SKIP", EDITION_ID, "a99")


def test_describe_in_plain_words():
    data = make_data()
    skip = learning.apply_signal(data, "SKIP", EDITION_ID, "a1")
    click = learning.apply_signal(data, "CLICK", EDITION_ID, "a2")
    assert learning.describe(skip) == "Skipped a Crypto story · Crypto −3"
    assert learning.describe(click) == "Read an AI Agents story · AI Agents +2 · Reuters +1"


def test_brain_shows_weights_and_last_10_signals_newest_first():
    data = make_data()
    for _ in range(6):
        learning.apply_signal(data, "SKIP", EDITION_ID, "a1")
        learning.apply_signal(data, "UNSKIP", EDITION_ID, "a1")
    learning.apply_signal(data, "CLICK", EDITION_ID, "a2")
    b = learning.brain(data)
    assert list(b["topic_weights"]) == ["AI Agents", "Crypto"]  # strongest first
    assert len(b["signals"]) == 10
    assert b["signals"][0]["action"] == "CLICK"
    assert b["signals"][0]["text"].startswith("Read an AI Agents story")


# ---------- API ----------

def test_signal_api_round_trip(client):
    store.save(make_data())
    response = client.post("/api/signal", json={"action": "SKIP", "edition_id": EDITION_ID, "article_id": "a1"})
    body = response.json()
    assert response.status_code == 200
    assert body["applied"] is True
    assert body["topic_weights"]["Crypto"] == 2
    assert body["signal"]["text"] == "Skipped a Crypto story · Crypto −3"
    # The edition on disk now has the story skipped.
    assert article(store.load(), "a1")["skipped"] is True
    # Repeating it is accepted but changes nothing.
    again = client.post("/api/signal", json={"action": "SKIP", "edition_id": EDITION_ID, "article_id": "a1"}).json()
    assert again["applied"] is False and again["topic_weights"]["Crypto"] == 2

    brain = client.get("/api/brain").json()
    assert brain["signals"][0]["text"] == "Skipped a Crypto story · Crypto −3"
    assert brain["max_weight"] == 25


def test_signal_api_errors(client):
    store.save(make_data())
    assert client.post("/api/signal", json={"action": "NOPE"}).status_code == 422
    assert client.post("/api/signal", json={"action": "SKIP"}).status_code == 422
    missing = client.post("/api/signal", json={"action": "SKIP", "edition_id": EDITION_ID, "article_id": "zz"})
    assert missing.status_code == 404
    # Nothing was written by the failed requests.
    assert store.load()["signals"] == []
