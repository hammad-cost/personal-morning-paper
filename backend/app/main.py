from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app import editions, gatherer, learning, ranker, store  # noqa: E402  (env must load first)
from app.models import OnboardRequest, SignalRequest, StateResponse, SwapRequest, UserProfile  # noqa: E402

app = FastAPI(title="The Personal Morning Paper")


def _state(data: dict) -> StateResponse:
    profile = UserProfile(**data["user"])
    today = editions.find_today(data)
    return StateResponse(
        onboarded=profile.onboarded,
        profile=profile,
        today_edition_id=today["id"] if today else None,
    )


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/state", response_model=StateResponse)
def get_state():
    return _state(store.load())


@app.post("/api/onboard", response_model=StateResponse)
def onboard(body: OnboardRequest):
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

    return _state(store.update(apply))


@app.post("/api/reset", response_model=StateResponse)
def reset():
    """Dev only: clear the store for a fresh demo."""
    editions.reset_status()
    return _state(store.reset())


@app.get("/api/edition/today")
def edition_today():
    """Today's edition, generated on first request of the day."""
    if not store.load()["user"]["onboarded"]:
        raise HTTPException(status_code=409, detail="Reader is not onboarded yet.")
    try:
        return editions.get_or_create_today()
    except editions.GenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/edition/{edition_id}/swap")
def swap(edition_id: str, body: SwapRequest):
    """Editor Desk: replace one story with a fresh one on a requested topic."""
    try:
        return editions.swap_story(edition_id, body.article_id, body.topic)
    except editions.SwapError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except editions.GenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/generation/status")
def generation_status():
    """Printing Press step for the loading screen."""
    return editions.get_status()


@app.post("/api/signal")
def signal(body: SignalRequest):
    """Record a reader action and update weights."""
    result = {}

    def apply(data: dict) -> None:
        result["signal"] = learning.apply_signal(data, **body.model_dump())
        result["topic_weights"] = data["user"]["topic_weights"]

    try:
        store.update(apply)
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
def brain():
    """Topic weights plus the last 10 signals in plain words."""
    return learning.brain(store.load())


@app.get("/api/debug/candidates")
def debug_candidates(limit: int = 50):
    """Dev only: what the gatherer found and what the ranker would print today."""
    data = store.load()
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
