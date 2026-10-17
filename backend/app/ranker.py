"""Rank candidate articles into a 10-story paper. Pure functions, no I/O.

score = topic_weight
      + recency_bonus   (3 if under 12 hours, 1.5 if under 24, else 0)
      + source_weight   (from clicks on that source)
      - seen_penalty    (10 if the URL appeared in an earlier edition)
      - domain_penalty  (1 if the source is a bare domain like "kpmg.com": Google News
                         names unregistered, often non-news sites that way)
"""

import re
from datetime import datetime, timezone

PAPER_SIZE = 10
MAX_PER_TOPIC = 3
MAX_PER_SOURCE_PER_TOPIC = 1  # one outlet never fills a section
EXPLORE_MAX_WEIGHT = 5  # "low or new" topics: weight 5 or less (unknown topics count as 0)
SEEN_PENALTY = 10
DOMAIN_PENALTY = 1
EXPLORE_LABEL = "Something new"
PHOTO_TIEBREAK = 0.99  # a real news photo wins only within ~1 point

_BARE_DOMAIN = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$", re.IGNORECASE)


def is_bare_domain(source_name: str) -> bool:
    return bool(_BARE_DOMAIN.match(source_name.strip()))


def recency_bonus(published_at: str, now: datetime) -> float:
    published = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    hours = (now - published).total_seconds() / 3600
    if hours < 12:
        return 3.0
    if hours < 24:
        return 1.5
    return 0.0


def score_article(article: dict, topic_weights: dict, source_weights: dict, seen_urls: set, now: datetime) -> float:
    score = (
        topic_weights.get(article["topic"], 0)
        + recency_bonus(article["published_at"], now)
        + source_weights.get(article["source_name"], 0)
        - (SEEN_PENALTY if article["url"] in seen_urls else 0)
        - (DOMAIN_PENALTY if is_bare_domain(article["source_name"]) else 0)
    )
    return round(score, 2)


def score_all(candidates, topic_weights, source_weights=None, seen_urls=None, now=None) -> list[dict]:
    """Score every non-blocked candidate; highest first."""
    source_weights = source_weights or {}
    seen_urls = seen_urls or set()
    now = now or datetime.now(timezone.utc)
    scored = [
        {**a, "score": score_article(a, topic_weights, source_weights, seen_urls, now)}
        for a in candidates
        if topic_weights.get(a["topic"], 0) >= 0
    ]
    scored.sort(key=_order)
    return scored


def _with_photo(a: dict) -> float:
    return a["score"] + (PHOTO_TIEBREAK if a.get("image_url") else 0)


def _order(a: dict):
    # Highest score first; near-ties go to stories with a real photo, then newer, then id.
    return (-_with_photo(a), _neg_time(a["published_at"]), a["id"])


def _neg_time(published_at: str) -> float:
    return -datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


def _pick_explore(scored: list[dict], picked: list[dict], topic_weights: dict) -> dict | None:
    picked_ids = {a["id"] for a in picked}
    picked_topics = {a["topic"] for a in picked}
    remaining = [a for a in scored if a["id"] not in picked_ids]
    low_or_new = [
        a for a in remaining
        if a["topic"] not in picked_topics and topic_weights.get(a["topic"], 0) <= EXPLORE_MAX_WEIGHT
    ]
    fresh_topic = [a for a in remaining if a["topic"] not in picked_topics]
    pool = low_or_new or fresh_topic
    return pool[0] if pool else None


def rank(candidates, topic_weights, source_weights=None, seen_urls=None, now=None,
         size=PAPER_SIZE, max_per_topic=MAX_PER_TOPIC) -> dict:
    """Pick the paper: top (size-1) by score with a per-topic cap, plus 1 explore story.

    Returns {"articles": [...], "sections": [...]} with the lead first, then stories
    grouped by section in section order.
    """
    scored = score_all(candidates, topic_weights, source_weights, seen_urls, now)

    picked: list[dict] = []
    per_topic: dict[str, int] = {}
    per_source: dict[tuple[str, str], int] = {}

    def fill(limit: int) -> None:
        """Add the best remaining stories that respect the per-topic and per-source caps."""
        taken = {a["id"] for a in picked}
        for article in scored:
            if len(picked) >= limit:
                return
            source_key = (article["topic"], article["source_name"])
            if article["id"] in taken or per_topic.get(article["topic"], 0) >= max_per_topic:
                continue
            if per_source.get(source_key, 0) >= MAX_PER_SOURCE_PER_TOPIC:
                continue
            picked.append({**article, "is_lead": False, "is_explore": False})
            per_topic[article["topic"]] = per_topic.get(article["topic"], 0) + 1
            per_source[source_key] = per_source.get(source_key, 0) + 1

    fill(size - 1)
    explore = _pick_explore(scored, picked, topic_weights)
    if explore:
        picked.append({**explore, "is_lead": False, "is_explore": True, "label": EXPLORE_LABEL})
    else:
        fill(size)  # no new topic left: use the spare slot for the next best story
    if not explore and len(picked) > 1:
        # Few candidates: every story is already in. Label the weakest low-weight one as the explore pick.
        low = [a for a in picked[1:] if topic_weights.get(a["topic"], 0) <= EXPLORE_MAX_WEIGHT]
        if low:
            weakest = min(low, key=lambda a: (topic_weights.get(a["topic"], 0), a["score"]))
            weakest.update(is_explore=True, label=EXPLORE_LABEL)

    if not picked:
        return {"articles": [], "sections": []}

    # The highest-scoring regular story leads (the explore story only leads if it is alone).
    regular = [a for a in picked if not a["is_explore"]] or picked
    lead = max(regular, key=_with_photo)
    lead["is_lead"] = True

    # Sections follow topic weight; ties broken by the section's best score.
    best = {}
    for a in picked:
        best[a["topic"]] = max(best.get(a["topic"], float("-inf")), a["score"])
    sections = sorted(best, key=lambda t: (-topic_weights.get(t, 0), -best[t], t))

    order = {t: i for i, t in enumerate(sections)}
    rest = sorted((a for a in picked if a is not lead), key=lambda a: (order[a["topic"]], -a["score"]))
    return {"articles": [lead, *rest], "sections": sections}
