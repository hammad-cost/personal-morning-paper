import json

from app import store


def test_creates_defaults_when_file_missing(temp_store):
    assert not temp_store.exists()
    data = store.load()
    assert data == store.defaults()
    assert temp_store.exists()
    assert json.loads(temp_store.read_text(encoding="utf-8")) == store.defaults()


def test_save_then_load_round_trips(temp_store):
    data = store.load()
    data["user"]["name"] = "Ayesha"
    store.save(data)
    assert store.load()["user"]["name"] == "Ayesha"


def test_update_applies_and_persists(temp_store):
    store.update(lambda d: d["signals"].append({"action": "CLICK"}))
    assert store.load()["signals"] == [{"action": "CLICK"}]


def test_fills_missing_keys_in_old_file(temp_store):
    temp_store.write_text(json.dumps({"user": {"onboarded": True}}), encoding="utf-8")
    data = store.load()
    assert data["user"]["onboarded"] is True
    assert data["user"]["topic_weights"] == {}
    assert data["editions"] == []
    assert data["signals"] == []


def test_reset_restores_defaults(temp_store):
    store.update(lambda d: d["user"].update(onboarded=True))
    store.reset()
    assert store.load() == store.defaults()


def test_defaults_are_independent_copies():
    a = store.defaults()
    a["user"]["topic_weights"]["X"] = 1
    assert store.defaults()["user"]["topic_weights"] == {}
