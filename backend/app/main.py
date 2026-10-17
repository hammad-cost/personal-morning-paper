from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app import auth, daily, editions, gatherer, learning, links, mailer, pdf, photos, ranker, store  # noqa: E402  (env must load first)
from app.models import OnboardRequest, SettingsRequest, SignalRequest, StateResponse, SwapRequest, UserProfile  # noqa: E402

MAX_MANUAL_EMAILS_PER_DAY = 5
_emails_saved: set[tuple[str, str]] = set()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    stop = daily.start_scheduler()  # morning papers by email, if email is set up
    yield
    if stop:
        stop.set()


app = FastAPI(title="Vale", lifespan=lifespan)


def reader(authorization: Annotated[str | None, Header()] = None) -> str:
    """The signed-in reader's id, or "local" when sign-in is not configured."""
    try:
        uid, email = auth.identity_for(authorization)
    except auth.NotSignedIn as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    # Keep the account's email on the profile so the morning job knows where to send.
    if email and (uid, email) not in _emails_saved:
        if store.load(uid)["user"].get("email") != email:
            store.update(lambda d: d["user"].update(email=email), uid)
        _emails_saved.add((uid, email))
    return uid


Reader = Annotated[str, Depends(reader)]


def _state(data: dict) -> StateResponse:
    profile = UserProfile(**data["user"])
    today = editions.find_today(data)
    return StateResponse(
        onboarded=profile.onboarded,
        profile=profile,
        today_edition_id=today["id"] if today else None,
        extra_editions_left=editions.extra_editions_left(data),
        email_ready=mailer.configured() and bool(profile.email),
    )


def _require_onboarded(uid: str) -> None:
    if not store.load(uid)["user"]["onboarded"]:
        raise HTTPException(status_code=409, detail="Reader is not onboarded yet.")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/state", response_model=StateResponse)
def get_state(uid: Reader):
    return _state(store.load(uid))


@app.post("/api/onboard", response_model=StateResponse)
def onboard(body: OnboardRequest, uid: Reader):
    def apply(data: dict) -> None:
        user = data["user"]
        user.update(
            onboarded=True,
            name=body.name,
            paper_title=(body.paper_title or "").strip() or f"THE {body.name.upper()} CHRONICLE",
            bio=body.bio,
            topic_weights=body.topic_weights,
        )
        if not user.get("created_at"):
            user["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return _state(store.update(apply, uid))


@app.post("/api/reset", response_model=StateResponse)
def reset(uid: Reader):
    """Start this reader over (dev/demo). Stored pictures are shared, so only local mode clears them."""
    editions.reset_status(uid)
    if uid == store.LOCAL_USER:
        photos.clear()
    return _state(store.reset(uid))


@app.get("/api/edition/today")
def edition_today(uid: Reader):
    """Today's edition, generated on first request of the day."""
    _require_onboarded(uid)
    try:
        return editions.get_or_create_today(uid)
    except editions.GenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/edition/next")
def edition_next(uid: Reader):
    """Print a new edition now using the updated weights (learning demo and archive)."""
    _require_onboarded(uid)
    try:
        return editions.create_next(uid)
    except editions.DailyLimitReached as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except editions.GenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/editions")
def editions_list(uid: Reader):
    """Past editions, newest first: id, number, date, lead headline."""
    return editions.list_editions(store.load(uid))


@app.get("/api/edition/{edition_id}")
def edition_by_id(edition_id: str, uid: Reader):
    """One full edition."""
    edition = editions.get_edition(store.load(uid), edition_id)
    if not edition:
        raise HTTPException(status_code=404, detail=f"Edition {edition_id} not found.")
    return editions.with_photos(edition, uid)


@app.get("/api/images/{name}")
def image(name: str):
    """A stored story picture. Public on purpose: <img> tags can't send a login, and the
    file names are content hashes that reveal nothing about any reader."""
    path = photos.local_name(name)
    if not path:
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/api/edition/{edition_id}/pdf")
def edition_pdf(edition_id: str, uid: Reader):
    """Download the edition as a broadsheet PDF, skipped stories excluded."""
    data = store.load(uid)
    edition = editions.get_edition(data, edition_id)
    if not edition:
        raise HTTPException(status_code=404, detail=f"Edition {edition_id} not found.")
    title = data["user"]["paper_title"]
    return Response(
        content=pdf.build_pdf(edition, title),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf.filename_for(edition, title)}"'},
    )


@app.post("/api/edition/{edition_id}/email")
def email_edition(edition_id: str, uid: Reader):
    """Email this edition (PDF attached) to the signed-in reader's own address."""
    data = store.load(uid)
    edition = editions.get_edition(data, edition_id)
    if not edition:
        raise HTTPException(status_code=404, detail=f"Edition {edition_id} not found.")
    today = daily.local_today()
    sent = data["user"].get("emails_sent", {}).get(today, 0)
    if sent >= MAX_MANUAL_EMAILS_PER_DAY:
        raise HTTPException(status_code=429, detail="That's enough emails for today. Try again tomorrow.")
    try:
        address = mailer.send_edition(uid, data["user"], editions.with_photos(edition, uid))
    except mailer.MailError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.update(lambda d: d["user"].update(emails_sent={today: sent + 1}), uid)
    return {"sent_to": address}


@app.get("/api/pdf/{token}")
def pdf_by_link(token: str):
    """The 7-day download link from an email: works without signing in, only for that paper."""
    try:
        link = links.read(token, "pdf")
    except links.BadLink as exc:
        raise HTTPException(status_code=403, detail=f"This download link doesn't work: {exc}.") from exc
    data = store.load(link["u"])
    edition = editions.get_edition(data, link["e"])
    if not edition:
        raise HTTPException(status_code=404, detail="That paper is no longer available.")
    title = data["user"]["paper_title"]
    return Response(content=pdf.build_pdf(edition, title), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{pdf.filename_for(edition, title)}"'})


@app.get("/api/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe(token: str):
    """One click from the email footer turns the morning email off."""
    try:
        link = links.read(token, "unsub")
    except links.BadLink:
        return HTMLResponse(_page("This link has expired", "Open Vale and switch daily emails off from your paper."), status_code=403)
    store.update(lambda d: d["user"].update(daily_email=False), link["u"])
    return _page("Daily emails are off", "You won't get your paper by email any more. You can switch it back on from your paper in Vale.")


def _page(title: str, body: str) -> str:
    return (f'<!doctype html><meta name="viewport" content="width=device-width"><title>Vale</title>'
            f'<body style="background:#FAF7F2;color:#1A1917;font-family:Georgia,serif;text-align:center;padding:60px 20px">'
            f'<div style="font-size:32px;font-weight:900">Vale</div>'
            f'<h1 style="border-top:4px double #1A1917;border-bottom:4px double #1A1917;padding:16px 0">{title}</h1>'
            f'<p>{body}</p><p><a href="{mailer.app_url()}" style="color:#1A1917">Open Vale</a></p></body>')


@app.post("/api/settings", response_model=StateResponse)
def settings(body: SettingsRequest, uid: Reader):
    """Reader preferences: the morning email on or off."""
    return _state(store.update(lambda d: d["user"].update(daily_email=body.daily_email), uid))


@app.post("/api/cron/daily")
def cron_daily(x_cron_secret: Annotated[str | None, Header()] = None):
    """For an outside scheduler: send today's morning papers. Needs the CRON_SECRET header."""
    import hmac
    import os

    secret = os.getenv("CRON_SECRET", "").strip()
    if not secret or not x_cron_secret or not hmac.compare_digest(x_cron_secret, secret):
        raise HTTPException(status_code=403, detail="Not allowed.")
    return daily.run()


@app.post("/api/edition/{edition_id}/swap")
def swap(edition_id: str, body: SwapRequest, uid: Reader):
    """Editor Desk: replace one story with a fresh one on a requested topic."""
    try:
        return editions.swap_story(edition_id, body.article_id, body.topic, uid)
    except editions.SwapError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except editions.GenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/generation/status")
def generation_status(uid: Reader):
    """Printing Press step for the loading screen."""
    return editions.get_status(uid)


@app.post("/api/signal")
def signal(body: SignalRequest, uid: Reader):
    """Record a reader action and update weights."""
    result = {}

    def apply(data: dict) -> None:
        result["signal"] = learning.apply_signal(data, **body.model_dump())
        result["topic_weights"] = data["user"]["topic_weights"]

    try:
        store.update(apply, uid)
    except learning.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except learning.SignalError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    sig = result["signal"]
    return {
        "applied": sig is not None,
        "signal": {**sig, "text": learning.describe(sig)} if sig else None,
        "topic_weights": result["topic_weights"],
    }


@app.get("/api/brain")
def brain(uid: Reader):
    """Topic weights plus the last 10 signals in plain words."""
    return learning.brain(store.load(uid))


@app.get("/api/debug/candidates")
def debug_candidates(uid: Reader, limit: int = 50):
    """Dev only: what the gatherer found and what the ranker would print today."""
    data = store.load(uid)
    user = data["user"]
    weights = user["topic_weights"]

    candidates = gatherer.gather(weights)
    paper = ranker.rank(candidates, weights, user["source_weights"], editions.seen_urls(data))
    scored = ranker.score_all(candidates, weights, user["source_weights"], editions.seen_urls(data))
    return {
        "topics_queried": gatherer.topics_to_query(weights),
        "blocked_topics": [t for t, w in weights.items() if w < 0],
        "candidate_count": len(candidates),
        "paper": paper,
        "candidates": scored[:limit],
    }
