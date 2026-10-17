from datetime import date, datetime, timezone

from fastapi import FastAPI

from app import store
from app.models import OnboardRequest, StateResponse, UserProfile

app = FastAPI(title="The Personal Morning Paper")


def _today_edition_id(data: dict) -> str | None:
    today = date.today().isoformat()
    todays = [e for e in data["editions"] if e.get("date") == today]
    return todays[-1]["id"] if todays else None


def _state(data: dict) -> StateResponse:
    profile = UserProfile(**data["user"])
    return StateResponse(
        onboarded=profile.onboarded,
        profile=profile,
        today_edition_id=_today_edition_id(data),
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
    return _state(store.reset())
