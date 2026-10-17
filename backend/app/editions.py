"""Build and store daily editions: gather -> rank -> write -> save.

Progress is published in `status` so the Printing Press screen can poll it.
A lock makes sure two requests on the same day never create two editions.
"""

import math
import threading
from datetime import date, datetime, timezone

from app import ai_editor, gatherer, ranker, store

STEPS = ["gathering", "choosing", "writing", "setting"]
WORDS_PER_MINUTE = 200

_generate_lock = threading.Lock()
_status_lock = threading.Lock()
_status = {"state": "idle", "step": None, "step_index": -1, "error": None, "edition_id": None}


class GenerationError(RuntimeError):
    pass


# ---------- status ----------

def get_status() -> dict:
    with _status_lock:
        return dict(_status)


def _set_status(**changes) -> None:
    with _status_lock:
        _status.update(changes)
        if "step" in changes:
            _status["step_index"] = STEPS.index(changes["step"]) if changes["step"] else -1


def reset_status() -> None:
    _set_status(state="idle", step=None, error=None, edition_id=None)


# ---------- helpers ----------

def today_str() -> str:
    return date.today().isoformat()


def find_today(data: dict) -> dict | None:
    todays = [e for e in data["editions"] if e.get("date") == today_str()]
    return todays[-1] if todays else None


def seen_urls(data: dict) -> set[str]:
    return {a["url"] for e in data["editions"] for a in e.get("articles", [])}


def reading_minutes(edition: dict) -> int:
    parts = [edition["connect_the_dots"]["text"], edition["mind_vitamin"]["content"]]
    parts += [t["text"] for t in edition["three_takeaways"]]
    for a in edition["articles"]:
        parts += [a["headline"], a["summary"], a["why_it_matters"]]
    words = sum(len(p.split()) for p in parts)
    return max(1, math.ceil(words / WORDS_PER_MINUTE))


def _assemble(data: dict, paper: dict, output: ai_editor.EditorOutput, writer: str) -> dict:
    copy = {a.id: a for a in output.articles}
    number = max((e.get("edition_number", 0) for e in data["editions"]), default=0) + 1
    same_day = sum(1 for e in data["editions"] if e.get("date") == today_str())
    articles = []
    for a in paper["articles"]:
        c = copy[a["id"]]
        articles.append({
            "id": a["id"],
            "topic": a["topic"],
            "headline": c.headline,
            "original_headline": a["headline"],
            "summary": c.summary,
            "why_it_matters": c.why_it_matters,
            "source_name": a["source_name"],
            "url": a["url"],
            "published_at": a["published_at"],
            "score": a["score"],
            "is_lead": a["is_lead"],
            "is_explore": a["is_explore"],
            "label": a.get("label"),
            "skipped": False,
            "clicked": False,
        })
    edition = {
        "id": f"ed-{today_str()}-{same_day + 1}",
        "edition_number": number,
        "date": today_str(),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "writer": writer,
        "three_takeaways": [t.model_dump() for t in output.three_takeaways],
        "connect_the_dots": output.connect_the_dots.model_dump(),
        "mind_vitamin": output.mind_vitamin.model_dump(),
        "recall_quiz": [q.model_dump() for q in output.recall_quiz],
        "sections": paper["sections"],
        "articles": articles,
    }
    edition["reading_minutes"] = reading_minutes(edition)
    return edition


# ---------- generation ----------

def generate(data: dict) -> dict:
    """Build a new edition from the current store data (does not save it)."""
    user = data["user"]
    weights = user["topic_weights"]

    _set_status(state="running", step="gathering", error=None, edition_id=None)
    candidates = gatherer.gather(weights)

    _set_status(step="choosing")
    paper = ranker.rank(candidates, weights, user["source_weights"], seen_urls(data))
    if len(paper["articles"]) < 3:
        raise GenerationError("Not enough fresh news found for your topics. Try again in a few minutes.")
    # Short ids (a1..a10) are easier for the model to cite and match the blueprint's data model.
    for i, a in enumerate(paper["articles"], start=1):
        a["id"] = f"a{i}"

    _set_status(step="writing")
    output, writer = ai_editor.write_edition(paper["articles"], user["bio"], weights)

    _set_status(step="setting")
    return _assemble(data, paper, output, writer)


def _generate_and_save() -> dict:
    try:
        edition = generate(store.load())
    except Exception as exc:
        _set_status(state="error", error=str(exc))
        raise
    store.update(lambda d: d["editions"].append(edition))
    _set_status(state="done", edition_id=edition["id"])
    return edition


def get_or_create_today() -> dict:
    """Return today's edition, generating it once if it does not exist yet."""
    existing = find_today(store.load())
    if existing:
        return existing
    with _generate_lock:
        # Another request may have finished generating while we waited for the lock.
        existing = find_today(store.load())
        if existing:
            return existing
        return _generate_and_save()
