import json
import time

import httpx
import pytest

from app import auth, gatherer, store

ALICE = "11111111-1111-1111-1111-111111111111"
BOB = "22222222-2222-2222-2222-222222222222"
TOKENS = {"token-alice": ALICE, "token-bob": BOB}


@pytest.fixture
def accounts(monkeypatch):
    """Sign-in on (Supabase URL set), file storage for signed-in readers, fake Supabase Auth."""
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.test")
    calls = []

    def fetch_user(token):
        calls.append(token)
        if token not in TOKENS:
            raise auth.NotSignedIn("session expired or invalid")
        return {"id": TOKENS[token], "email": f"{token}@example.com"}

    monkeypatch.setattr(auth, "fetch_user", fetch_user)
    return calls


def as_(token):
    return {"Authorization": f"Bearer {token}"}


PROFILE = {"name": "Alice", "topic_weights": {"AI Agents": 10}}


def test_local_mode_needs_no_sign_in(client):
    assert client.get("/api/state").status_code == 200


def test_sign_in_is_required_when_accounts_are_on(client, accounts):
    assert client.get("/api/state").status_code == 401
    assert client.get("/api/state", headers={"Authorization": "Basic xyz"}).status_code == 401
    bad = client.get("/api/state", headers=as_("expired"))
    assert bad.status_code == 401 and "session" in bad.json()["detail"]
    assert client.get("/api/health").status_code == 200  # health stays public


def test_each_reader_has_their_own_paper(client, accounts):
    client.post("/api/onboard", json=PROFILE, headers=as_("token-alice"))
    alice = client.get("/api/state", headers=as_("token-alice")).json()
    bob = client.get("/api/state", headers=as_("token-bob")).json()
    assert alice["onboarded"] is True and alice["profile"]["paper_title"] == "THE ALICE CHRONICLE"
    assert bob["onboarded"] is False  # Bob never sees Alice's profile
    # The local single-reader store is untouched.
    assert store.load()["user"]["onboarded"] is False


def test_readers_cannot_open_each_others_editions(client, accounts, monkeypatch):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    monkeypatch.setattr(gatherer, "gather", lambda w: [
        {"id": f"h{i}", "topic": ["AI Agents", "Space", "Other", "More"][i % 4], "headline": f"Story {i}", "text": "",
         "source_name": f"Outlet {i}", "url": f"https://news.test/{i}", "published_at": now, "image_url": None}
        for i in range(12)
    ])
    client.post("/api/onboard", json=PROFILE, headers=as_("token-alice"))
    edition = client.get("/api/edition/today", headers=as_("token-alice")).json()
    assert client.get(f"/api/edition/{edition['id']}", headers=as_("token-alice")).status_code == 200
    assert client.get(f"/api/edition/{edition['id']}", headers=as_("token-bob")).status_code == 404
    assert client.get("/api/editions", headers=as_("token-bob")).json() == []
    # Each reader's Printing Press status is their own.
    assert client.get("/api/generation/status", headers=as_("token-bob")).json()["state"] == "idle"


def test_verified_tokens_are_cached(client, accounts):
    for _ in range(3):
        client.get("/api/state", headers=as_("token-alice"))
    assert accounts == ["token-alice"]  # Supabase Auth asked once


def test_unexpected_auth_errors_mean_signed_out(client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.test")

    def broken(token):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(auth, "fetch_user", broken)
    assert client.get("/api/state", headers=as_("anything")).status_code == 401


def test_user_ids_are_validated_for_file_storage():
    with pytest.raises(ValueError):
        store.load("../../etc/passwd")


# ---------- Supabase table storage ----------

def test_signed_in_readers_are_stored_in_supabase(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_TEST")
    rows = {}
    requests = []

    def fake_get(url, params=None, headers=None, timeout=None):
        requests.append(("GET", url, params, headers))
        uid = params["user_id"].removeprefix("eq.")
        body = [{"data": rows[uid]}] if uid in rows else []
        return httpx.Response(200, json=body, request=httpx.Request("GET", url))

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        requests.append(("POST", url, params, headers))
        rows[json["user_id"]] = json["data"]
        return httpx.Response(201, request=httpx.Request("POST", url))

    monkeypatch.setattr(store.httpx, "get", fake_get)
    monkeypatch.setattr(store.httpx, "post", fake_post)

    store.update(lambda d: d["user"].update(name="Alice"), ALICE)
    assert rows[ALICE]["user"]["name"] == "Alice"
    assert store.load(ALICE)["user"]["name"] == "Alice"

    method, url, params, headers = requests[-1]
    assert url == "https://project.supabase.test/rest/v1/vale_readers"
    assert headers["apikey"] == "sb_secret_TEST"
    assert "Authorization" not in headers  # new-style secret keys go only in apikey
    post = next(r for r in requests if r[0] == "POST")
    assert post[2] == {"on_conflict": "user_id"} and "merge-duplicates" in post[3]["Prefer"]
    # The local reader still uses its file, never Supabase.
    before = len(requests)
    store.load()
    assert len(requests) == before


def test_legacy_service_role_keys_also_go_in_authorization(monkeypatch):
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "eyJhbGciOiJIUzI1NiJ9.legacy.key")
    headers = store._headers("eyJhbGciOiJIUzI1NiJ9.legacy.key")
    assert headers["Authorization"] == "Bearer eyJhbGciOiJIUzI1NiJ9.legacy.key"


def test_schema_keeps_the_table_private():
    sql = (store.Path(__file__).parent.parent / "supabase" / "schema.sql").read_text(encoding="utf-8")
    assert "create table if not exists public.vale_readers" in sql
    assert "enable row level security" in sql
    assert "create policy" not in sql.lower()  # no browser access at all
    json.dumps(sql)  # plain text, nothing secret
