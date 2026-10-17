"""Build and store daily editions: gather -> rank -> write -> save.

Progress is published in `status` so the Printing Press screen can poll it.
A lock makes sure two requests on the same day never create two editions.
"""

import math
import os
import threading
from datetime import date, datetime, timezone

from app import ai_editor, gatherer, images, photos, ranker, store

STEPS = ["gathering", "choosing", "writing", "setting"]
PHOTO_CANDIDATES = 18  # strongest candidates checked for real photos before choosing
WORDS_PER_MINUTE = 200

_generate_lock = threading.Lock()
_status_lock = threading.Lock()
_status = {"state": "idle", "step": None, "step_index": -1, "error": None, "edition_id": None}


class GenerationError(RuntimeError):
    pass


class DailyLimitReached(RuntimeError):
    pass


LIMIT_MESSAGE = "That's today's paper. See you tomorrow."


def max_extra_per_day() -> int:
    """Extra editions allowed after the morning one (MAX_EXTRA_EDITIONS_PER_DAY, default 2)."""
    try:
        return max(0, int(os.getenv("MAX_EXTRA_EDITIONS_PER_DAY", "2")))
    except ValueError:
        return 2


def extra_editions_left(data: dict) -> int:
    printed_today = sum(1 for e in data["editions"] if e.get("date") == date.today().isoformat())
    # The morning edition is free; each one after it uses up an extra.
    return max(0, max_extra_per_day() - max(0, printed_today - 1))


def _attempt(fn):
    try:
        return fn()
    except Exception:
        return None


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
            "image_url": a.get("image_url"),
            "publisher_url": a.get("publisher_url"),
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
    # Look for real photos among the strongest candidates first, so near-ties can favour them.
    scored = ranker.score_all(candidates, weights, user["source_weights"], seen_urls(data))
    top = {a["id"] for a in scored[:PHOTO_CANDIDATES]}
    _attempt(lambda: images.enrich([c for c in candidates if c["id"] in top]))
    paper = ranker.rank(candidates, weights, user["source_weights"], seen_urls(data))
    if len(paper["articles"]) < 3:
        raise GenerationError("Not enough fresh news found for your topics. Try again in a few minutes.")
    # Short ids (a1..a10) are easier for the model to cite and match the blueprint's data model.
    for i, a in enumerate(paper["articles"], start=1):
        a["id"] = f"a{i}"

    _set_status(step="writing")
    output, writer = ai_editor.write_edition(paper["articles"], user["bio"], weights)

    _set_status(step="setting")
    edition = _assemble(data, paper, output, writer)
    # Every story gets a stored picture: news photo, subject photo, topic photo or Vale illustration.
    photos.ensure(
        edition["articles"],
        {a.id: a.image_subject for a in output.articles},
        {s.topic: s.wikipedia_title for s in output.section_photos},
    )
    return edition


def _generate_and_save() -> dict:
    try:
        edition = generate(store.load())
    except Exception as exc:
        _set_status(state="error", error=str(exc))
        raise
    store.update(lambda d: d["editions"].append(edition))
    _set_status(state="done", edition_id=edition["id"])
    return edition


class SwapError(LookupError):
    pass


def _find(data: dict, edition_id: str, article_id: str) -> tuple[dict, dict]:
    edition = next((e for e in data["editions"] if e["id"] == edition_id), None)
    if not edition:
        raise SwapError(f"edition {edition_id} not found")
    article = next((a for a in edition["articles"] if a["id"] == article_id), None)
    if not article:
        raise SwapError(f"article {article_id} not found in {edition_id}")
    return edition, article


def _resection(edition: dict, weights: dict) -> list[str]:
    """Keep the existing section order; drop empty ones and append new topics by weight."""
    topics = {a["topic"] for a in edition["articles"]}
    kept = [s for s in edition["sections"] if s in topics]
    new = sorted(topics - set(kept), key=lambda t: -weights.get(t, 0))
    return kept + new


def swap_story(edition_id: str, article_id: str, topic: str) -> dict:
    """Replace one story with a fresh one on `topic`; every other story stays as it was."""
    topic = topic.strip()
    if not topic:
        raise SwapError("a topic is needed to swap a story")
    data = store.load()
    edition, old = _find(data, edition_id, article_id)
    user = data["user"]
    weights = user["topic_weights"]
    # Match a known topic case-insensitively; a new one is title-cased for its section header
    # ("climate tech" -> "Climate Tech", acronyms like "AI" kept) and ranked at a neutral weight.
    known = next((t for t in weights if t.lower() == topic.lower()), None)
    topic = known or " ".join(w if w.isupper() else w[:1].upper() + w[1:] for w in topic.split())

    candidates = [
        a for a in gatherer.gather({topic: max(weights.get(topic, 0), 5)}) if a["topic"].lower() == topic.lower()
    ]
    used = seen_urls(data)
    fresh = [a for a in candidates if a["url"] not in used]
    scored = ranker.score_all(fresh, {topic: max(weights.get(topic, 0), 5)}, user["source_weights"])
    if not scored:
        raise GenerationError(f"No fresh story found on {topic} right now.")
    pick = {**scored[0], "id": old["id"]}

    others = [a["source_name"] for a in edition["articles"] if a["id"] != old["id"]]
    _attempt(lambda: images.enrich([pick]))
    out, writer = ai_editor.write_story(pick, user["bio"], weights, others)
    swapped = {"id": old["id"], "topic": topic, "source_name": pick["source_name"], "image_url": pick.get("image_url")}
    photos.ensure([swapped], {old["id"]: out.article.image_subject})

    def apply(d: dict) -> None:
        ed, current = _find(d, edition_id, article_id)
        current.clear()
        current.update({
            "id": old["id"],
            "topic": topic,
            "headline": out.article.headline,
            "original_headline": pick["headline"],
            "summary": out.article.summary,
            "why_it_matters": out.article.why_it_matters,
            "source_name": pick["source_name"],
            "url": pick["url"],
            "published_at": pick["published_at"],
            "image_url": swapped["image_url"],
            "image_credit": swapped["image_credit"],
            "image_kind": swapped["image_kind"],
            "image_source_url": swapped["image_source_url"],
            "publisher_url": pick.get("publisher_url"),
            "score": pick["score"],
            "is_lead": old.get("is_lead", False),
            "is_explore": False,
            "label": None,
            "skipped": False,
            "clicked": False,
            "swapped": True,
            "writer": writer,
        })
        # Takeaways and quiz questions about the old story now describe the new one.
        ed["three_takeaways"] = [
            out.takeaway.model_dump() if t["article_id"] == article_id else t for t in ed["three_takeaways"]
        ]
        ed["recall_quiz"] = [
            out.quiz.model_dump() if q["article_id"] == article_id else q for q in ed["recall_quiz"]
        ]
        dots = ed.get("connect_the_dots") or {}
        if article_id in dots.get("article_ids", []):
            dots["article_ids"] = [i for i in dots["article_ids"] if i != article_id]
        ed["sections"] = _resection(ed, d["user"]["topic_weights"])
        ed["reading_minutes"] = reading_minutes(ed)
        result["edition"] = ed

    result: dict = {}
    store.update(apply)
    return result["edition"]


def list_editions(data: dict) -> list[dict]:
    """Archive rows, newest first."""
    rows = []
    for e in sorted(data["editions"], key=lambda e: e.get("edition_number", 0), reverse=True):
        lead = next((a for a in e["articles"] if a.get("is_lead")), e["articles"][0] if e["articles"] else None)
        rows.append({
            "id": e["id"],
            "edition_number": e.get("edition_number"),
            "date": e.get("date"),
            "created_at": e.get("created_at"),
            "reading_minutes": e.get("reading_minutes"),
            "writer": e.get("writer"),
            "lead_headline": lead["headline"] if lead else None,
            "sections": e.get("sections", []),
        })
    return rows


def get_edition(data: dict, edition_id: str) -> dict | None:
    return next((e for e in data["editions"] if e["id"] == edition_id), None)


def create_next() -> dict:
    """Print a new edition now with the current weights, within the daily limit."""
    with _generate_lock:
        data = store.load()
        if find_today(data) and extra_editions_left(data) == 0:
            raise DailyLimitReached(LIMIT_MESSAGE)
        return _generate_and_save()


def with_photos(edition: dict | None) -> dict | None:
    """Editions printed before photos existed get pictures the first time they are opened."""
    if not edition or all(photos.is_local(a.get("image_url")) for a in edition["articles"]):
        return edition
    articles = [dict(a) for a in edition["articles"]]
    photos.ensure(articles)

    def apply(d: dict) -> None:
        saved = next((e for e in d["editions"] if e["id"] == edition["id"]), None)
        if saved:
            saved["articles"] = articles

    store.update(apply)
    return {**edition, "articles": articles}


def get_or_create_today() -> dict:
    """Return today's edition, generating it once if it does not exist yet."""
    existing = find_today(store.load())
    if existing:
        return with_photos(existing)
    with _generate_lock:
        # Another request may have finished generating while we waited for the lock.
        existing = find_today(store.load())
        if existing:
            return existing
        return _generate_and_save()
