import base64
import time
from datetime import datetime

import pytest

from app import auth, daily, gatherer, links, mailer, store
from app.daily import ZoneInfo

ALICE = "11111111-1111-1111-1111-111111111111"
BOB = "22222222-2222-2222-2222-222222222222"
TOKENS = {"token-alice": (ALICE, "alice@uni.edu"), "token-bob": (BOB, "bob@uni.edu")}


def as_(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def accounts(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.test")
    monkeypatch.setattr(auth, "fetch_user", lambda t: {"id": TOKENS[t][0], "email": TOKENS[t][1]} if t in TOKENS
                        else (_ for _ in ()).throw(auth.NotSignedIn("bad")))


@pytest.fixture
def brevo(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "xkeysib-test")
    monkeypatch.setenv("MAIL_FROM_EMAIL", "papers@vale.test")
    sent = []
    monkeypatch.setattr(mailer, "send_via_brevo", lambda message: sent.append(message) or {"messageId": "x"})
    return sent


@pytest.fixture
def news(monkeypatch):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    monkeypatch.setattr(gatherer, "gather", lambda w: [
        {"id": f"h{i}", "topic": ["AI Agents", "Space", "Other", "More"][i % 4], "headline": f"Story {i}", "text": "",
         "source_name": f"Outlet {i}", "url": f"https://news.test/{i}", "published_at": now, "image_url": None}
        for i in range(12)
    ])


def onboard(client, token="token-alice", name="Alice"):
    client.post("/api/onboard", json={"name": name, "topic_weights": {"AI Agents": 10}}, headers=as_(token))


# ---------- signed links ----------

def test_links_round_trip_and_refuse_tampering(monkeypatch):
    token = links.make("pdf", ALICE, "ed-1")
    assert links.read(token, "pdf") == {**links.read(token, "pdf"), "u": ALICE, "e": "ed-1"}
    with pytest.raises(links.BadLink):
        links.read(token, "unsub")  # a download link can't unsubscribe
    payload, sig = token.split(".")
    forged = links.make("pdf", BOB, "ed-1").split(".")[0] + "." + sig
    with pytest.raises(links.BadLink):
        links.read(forged, "pdf")  # someone else's id with Alice's signature
    with pytest.raises(links.BadLink):
        links.read("garbage", "pdf")
    monkeypatch.setattr(links.time, "time", lambda: 10**12)
    with pytest.raises(links.BadLink, match="expired"):
        links.read(token, "pdf")


# ---------- the email ----------

def edition():
    return {
        "id": "ed-2026-10-17-1", "edition_number": 1, "date": "2026-10-17", "reading_minutes": 4, "sections": ["AI"],
        "three_takeaways": [{"text": "Agents got a seed round.", "article_id": "a1"}],
        "connect_the_dots": {}, "mind_vitamin": {}, "recall_quiz": [],
        "articles": [{"id": "a1", "topic": "AI", "headline": "Lead <story>", "summary": "Calm summary.",
                      "source_name": "X", "url": "https://x.test", "is_lead": True, "skipped": False}],
    }


def test_message_has_newspaper_html_links_and_the_pdf(brevo):
    msg = mailer.build_message(ALICE, {"name": "Alice", "paper_title": "The Alice Times"}, edition(), "alice@uni.edu")
    assert msg["to"] == [{"email": "alice@uni.edu", "name": "Alice"}]
    assert msg["sender"] == {"name": "Vale", "email": "papers@vale.test"}
    assert "THE ALICE TIMES" in msg["subject"] and "Edition No. 1" in msg["subject"]
    assert "Agents got a seed round." in msg["htmlContent"]
    assert "Lead &lt;story&gt;" in msg["htmlContent"]  # escaped, not raw HTML
    assert "/api/pdf/" in msg["htmlContent"] and "/api/unsubscribe/" in msg["htmlContent"]
    assert msg["headers"]["List-Unsubscribe"].startswith("<http://localhost:5173/api/unsubscribe/")
    attachment = msg["attachment"][0]
    assert attachment["name"] == "the-alice-times-edition-1.pdf"
    assert base64.b64decode(attachment["content"]).startswith(b"%PDF")


def test_send_needs_email_setup_and_an_address(monkeypatch):
    with pytest.raises(mailer.MailError, match="not set up"):
        mailer.send_edition(ALICE, {"email": "a@b.co"}, edition())
    monkeypatch.setenv("BREVO_API_KEY", "k")
    monkeypatch.setenv("MAIL_FROM_EMAIL", "from@vale.test")
    with pytest.raises(mailer.MailError, match="no email"):
        mailer.send_edition(ALICE, {"email": ""}, edition())


# ---------- API ----------

def test_sign_in_saves_the_email_and_state_reports_email_ready(client, accounts, brevo):
    state = client.get("/api/state", headers=as_("token-alice")).json()
    assert state["profile"]["email"] == "alice@uni.edu"
    assert state["profile"]["daily_email"] is True
    assert state["email_ready"] is True


def test_email_this_paper_goes_only_to_the_readers_own_address(client, accounts, brevo, news):
    onboard(client)
    ed = client.get("/api/edition/today", headers=as_("token-alice")).json()
    r = client.post(f"/api/edition/{ed['id']}/email", headers=as_("token-alice"))
    assert r.status_code == 200 and r.json() == {"sent_to": "alice@uni.edu"}
    assert brevo[-1]["to"][0]["email"] == "alice@uni.edu"
    # Bob can't email Alice's edition (it isn't in his paper).
    assert client.post(f"/api/edition/{ed['id']}/email", headers=as_("token-bob")).status_code == 404


def test_manual_emails_are_capped_per_day(client, accounts, brevo, news):
    onboard(client)
    ed = client.get("/api/edition/today", headers=as_("token-alice")).json()
    for _ in range(5):
        assert client.post(f"/api/edition/{ed['id']}/email", headers=as_("token-alice")).status_code == 200
    capped = client.post(f"/api/edition/{ed['id']}/email", headers=as_("token-alice"))
    assert capped.status_code == 429


def test_local_reader_without_email_gets_a_clear_message(client, brevo, news):
    client.post("/api/onboard", json={"name": "Local", "topic_weights": {"AI Agents": 10}})
    ed = client.get("/api/edition/today").json()
    r = client.post(f"/api/edition/{ed['id']}/email")
    assert r.status_code == 400 and "no email" in r.json()["detail"]


def test_download_link_works_without_sign_in_but_only_for_that_paper(client, accounts, brevo, news):
    onboard(client)
    ed = client.get("/api/edition/today", headers=as_("token-alice")).json()
    good = client.get(f"/api/pdf/{links.make('pdf', ALICE, ed['id'])}")
    assert good.status_code == 200 and good.content.startswith(b"%PDF")
    assert client.get(f"/api/pdf/{links.make('pdf', ALICE, ed['id'])}x").status_code == 403
    assert client.get(f"/api/pdf/{links.make('unsub', ALICE)}").status_code == 403
    assert client.get(f"/api/pdf/{links.make('pdf', BOB, ed['id'])}").status_code == 404


def test_unsubscribe_link_turns_daily_email_off(client, accounts, brevo):
    client.get("/api/state", headers=as_("token-alice"))
    page = client.get(f"/api/unsubscribe/{links.make('unsub', ALICE, days=365)}")
    assert page.status_code == 200 and "Daily emails are off" in page.text
    assert store.load(ALICE)["user"]["daily_email"] is False
    assert client.get("/api/unsubscribe/broken").status_code == 403


def test_settings_switch_daily_email(client, accounts):
    off = client.post("/api/settings", json={"daily_email": False}, headers=as_("token-alice")).json()
    assert off["profile"]["daily_email"] is False
    on = client.post("/api/settings", json={"daily_email": True}, headers=as_("token-alice")).json()
    assert on["profile"]["daily_email"] is True


def test_cron_endpoint_needs_the_secret(client, monkeypatch, brevo):
    assert client.post("/api/cron/daily").status_code == 403
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    assert client.post("/api/cron/daily", headers={"X-Cron-Secret": "wrong"}).status_code == 403
    r = client.post("/api/cron/daily", headers={"X-Cron-Secret": "s3cret"})
    assert r.status_code == 200 and r.json()["sent"] == 0


# ---------- the morning job ----------

def seed_reader(uid, email, **extra):
    store.update(lambda d: d["user"].update(onboarded=True, name=uid[:4], email=email,
                                             topic_weights={"AI Agents": 10}, **extra), uid)


def test_morning_run_emails_each_reader_once(brevo, news):
    seed_reader(ALICE, "alice@uni.edu")
    seed_reader(BOB, "bob@uni.edu", daily_email=False)  # switched off
    first = daily.run()
    assert first["sent"] == 1 and [m["to"][0]["email"] for m in brevo] == ["alice@uni.edu"]
    assert store.load(ALICE)["user"]["last_daily_email"] == first["day"]
    assert store.load(ALICE)["editions"]  # today's paper was printed for her
    again = daily.run()
    assert again["sent"] == 0 and len(brevo) == 1  # never twice in a day


def test_one_failure_does_not_stop_the_others(monkeypatch, news):
    monkeypatch.setenv("BREVO_API_KEY", "k")
    monkeypatch.setenv("MAIL_FROM_EMAIL", "from@vale.test")
    seed_reader(ALICE, "alice@uni.edu")
    seed_reader(BOB, "bob@uni.edu")
    sent = []

    def flaky(message):
        if message["to"][0]["email"] == "alice@uni.edu":
            raise mailer.MailError("mailbox full")
        sent.append(message)

    monkeypatch.setattr(mailer, "send_via_brevo", flaky)
    result = daily.run()
    assert result["sent"] == 1 and len(result["errors"]) == 1
    assert "last_daily_email" not in store.load(ALICE)["user"]  # she'll be retried next run


def test_due_only_after_the_morning_hour(monkeypatch):
    monkeypatch.setenv("DAILY_EMAIL_HOUR", "7")
    tz = ZoneInfo("Asia/Karachi")
    monkeypatch.setattr(daily, "_last_run_day", None)
    assert not daily.due(datetime(2026, 10, 17, 6, 59, tzinfo=tz))
    assert daily.due(datetime(2026, 10, 17, 7, 0, tzinfo=tz))
    monkeypatch.setattr(daily, "_last_run_day", "2026-10-17")
    assert not daily.due(datetime(2026, 10, 17, 9, 0, tzinfo=tz))  # already ran today
    assert daily.due(datetime(2026, 10, 18, 7, 5, tzinfo=tz))


def test_scheduler_stays_off_without_email_setup():
    assert daily.start_scheduler() is None
