"""Learning signals: reader actions change topic and source weights.

| Signal      | Topic delta | Other effect                                  |
| CLICK       | +2          | source weight +1, article marked clicked      |
| LIKE        | +2          | source weight +1, article marked liked (feed ♡) |
| UNLIKE      | -2          | source weight -1, reverses the like           |
| SKIP        | -3          | article marked skipped (hidden, left out of PDF) |
| UNSKIP      | +3          | reverses the skip                             |
| QUIZ_RIGHT  | +1          |                                               |
| QUIZ_WRONG  | 0           | logged only                                   |
| COPILOT     | +5 or -5    | logged with the reader's words                |

Weights are clamped to [-15, 25]. Repeating a CLICK, LIKE or SKIP on the same story,
or undoing a skip or like that isn't there, changes nothing.
"""

from datetime import datetime, timezone

MIN_WEIGHT = -15
MAX_WEIGHT = 25
COPILOT_STEP = 5
BRAIN_SIGNALS = 10

TOPIC_DELTA = {"CLICK": 2, "LIKE": 2, "UNLIKE": -2, "SKIP": -3, "UNSKIP": 3, "QUIZ_RIGHT": 1, "QUIZ_WRONG": 0}
ACTIONS = set(TOPIC_DELTA) | {"COPILOT"}
ARTICLE_ACTIONS = set(TOPIC_DELTA)


class SignalError(ValueError):
    """Bad request: unknown action, missing article, wrong delta."""


class NotFound(LookupError):
    pass


def clamp(weight: float) -> int:
    return int(max(MIN_WEIGHT, min(MAX_WEIGHT, round(weight))))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_article(data: dict, edition_id: str, article_id: str) -> dict:
    edition = next((e for e in data["editions"] if e["id"] == edition_id), None)
    if not edition:
        raise NotFound(f"edition {edition_id} not found")
    article = next((a for a in edition["articles"] if a["id"] == article_id), None)
    if not article:
        raise NotFound(f"article {article_id} not found in {edition_id}")
    return article


def _adjust(weights: dict, key: str, delta: int) -> int:
    """Apply delta with clamping; return the change that actually happened."""
    before = weights.get(key, 0)
    after = clamp(before + delta)
    weights[key] = after
    return after - before


def apply_signal(data: dict, action: str, edition_id: str | None = None, article_id: str | None = None,
                 topic: str | None = None, delta: int | None = None, note: str = "") -> dict | None:
    """Mutate store data for one signal. Returns the logged signal, or None if it was a no-op."""
    if action not in ACTIONS:
        raise SignalError(f"unknown action {action!r}")
    user = data["user"]
    weights = user["topic_weights"]
    article = None

    if action in ARTICLE_ACTIONS:
        if not edition_id or not article_id:
            raise SignalError(f"{action} needs edition_id and article_id")
        article = _find_article(data, edition_id, article_id)
        topic = article["topic"]
        # Repeats are no-ops so a double click or a stale undo can't skew the weights.
        if action == "CLICK" and article.get("clicked"):
            return None
        if action == "SKIP" and article.get("skipped"):
            return None
        if action == "UNSKIP" and not article.get("skipped"):
            return None
        if action == "LIKE" and article.get("liked"):
            return None
        if action == "UNLIKE" and not article.get("liked"):
            return None
        wanted = TOPIC_DELTA[action]
    else:  # COPILOT
        topic = (topic or "").strip()
        if not topic:
            raise SignalError("COPILOT needs a topic")
        if delta not in (COPILOT_STEP, -COPILOT_STEP):
            raise SignalError(f"COPILOT delta must be +{COPILOT_STEP} or -{COPILOT_STEP}")
        # Match an existing topic case-insensitively so "quantum computing" hits "Quantum Computing".
        topic = next((t for t in weights if t.lower() == topic.lower()), topic)
        wanted = delta

    applied = _adjust(weights, topic, wanted) if wanted else 0
    signal = {
        "ts": _now(),
        "edition_id": edition_id,
        "article_id": article_id,
        "topic": topic,
        "action": action,
        "requested": wanted,
        "delta": applied,
        "weight": weights.get(topic, 0),
    }

    if article is not None:
        signal["headline"] = article["headline"]
        if action == "CLICK":
            article["clicked"] = True
            source = article.get("source_name")
            if source:
                signal["source"] = source
                signal["source_delta"] = _adjust(user["source_weights"], source, 1)
        elif action in ("LIKE", "UNLIKE"):
            article["liked"] = action == "LIKE"
            source = article.get("source_name")
            if source:
                signal["source"] = source
                signal["source_delta"] = _adjust(user["source_weights"], source, 1 if action == "LIKE" else -1)
        elif action == "SKIP":
            article["skipped"] = True
        elif action == "UNSKIP":
            article["skipped"] = False
    if note:
        signal["note"] = note.strip()[:200]

    data["signals"].append(signal)
    return signal


def _signed(n: int) -> str:
    return f"+{n}" if n > 0 else ("−" + str(abs(n)) if n < 0 else "±0")


def _a(word: str) -> str:
    return f"an {word}" if word[:1].lower() in "aeiou" else f"a {word}"


def describe(signal: dict) -> str:
    """Plain words for the Brain panel, e.g. 'Skipped a Crypto story · Crypto −3'."""
    topic, delta = signal["topic"], _signed(signal["delta"])
    what = {
        "CLICK": f"Read {_a(topic)} story",
        "SKIP": f"Skipped {_a(topic)} story",
        "UNSKIP": f"Undid a skip on {_a(topic)} story",
        "LIKE": f"Liked {_a(topic)} story",
        "UNLIKE": f"Took back a like on {_a(topic)} story",
        "QUIZ_RIGHT": f"Remembered a {topic} story",
        "QUIZ_WRONG": f"Missed a quiz question on {topic}",
        "COPILOT": f"Asked the Editor for {'more' if signal.get('requested', 0) > 0 else 'less'} {topic}",
    }[signal["action"]]
    if signal["action"] == "COPILOT" and signal.get("note"):
        what = f"Told the Editor “{signal['note']}”"
    text = f"{what} · {topic} {delta}"
    if signal.get("source_delta"):
        text += f" · {signal['source']} {_signed(signal['source_delta'])}"
    return text


def brain(data: dict) -> dict:
    user = data["user"]
    recent = list(reversed(data["signals"][-BRAIN_SIGNALS:]))
    return {
        "topic_weights": dict(sorted(user["topic_weights"].items(), key=lambda kv: -kv[1])),
        "source_weights": dict(sorted(user["source_weights"].items(), key=lambda kv: -kv[1])),
        "signals": [{**s, "text": describe(s)} for s in recent],
        "min_weight": MIN_WEIGHT,
        "max_weight": MAX_WEIGHT,
    }
