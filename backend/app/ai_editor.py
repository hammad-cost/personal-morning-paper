"""The only module that talks to an AI model.

One call per edition: the model writes summaries, takeaways, connect-the-dots, a mind
vitamin and a recall quiz from the fetched RSS text only. The reply is strict JSON,
validated with Pydantic and checked against the real article ids. On failure it retries
once, then falls back to plain RSS text with no AI writing.
"""

import json
import logging
import os

from pydantic import BaseModel, Field, ValidationError

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-flash-latest"
MAX_ATTEMPTS = 2  # first try + one retry

SYSTEM_PROMPT = """You are the editor of a calm, personal morning newspaper written for one reader.
Write in a calm, clear newspaper style. Rules:
- Use ONLY facts found in the article text you are given. If the text is thin, say less; never fill gaps.
- Never invent numbers, names, quotes or dates.
- Keep each headline's original meaning; you may tighten wording.
- summary: 2-3 sentences. why_it_matters: 1 sentence tied to this reader's interests.
- Write exactly 3 three_takeaways; each must cite a real article_id.
- Articles come in part 1 and part 2 (the reader takes a 3-question Brain check after each part). Write 3 recall_quiz
  questions about part-1 articles, then 3 about part-2 articles (6 in total; only 3 if there is no part 2).
  Every question must cite a real article_id from the part it belongs to.
- recall_quiz: 3 options each, answer_index is the 0-based index of the correct option, answerable from the summaries.
- connect_the_dots: 1-2 sentences linking two or more stories; cite their article_ids.
- mind_vitamin: a short, calm, practical thought for the day (not news).
- Return every article id you were given exactly once in "articles".
- image_subject: the story's main real-world subject that a photo could show (a company, person, product, place or object), 1-4 words, named as on Wikipedia, e.g. "Palo Alto Networks" or "SpaceX Starship". Use "" if there is no clear subject.
- section_photos: for each topic in the paper, the English Wikipedia article whose photo best represents that topic as news (e.g. Space -> "Spaceflight", Cybersecurity -> "Computer security", AI Agents -> "Intelligent agent")."""


# ---------- output schema ----------

class ArticleCopy(BaseModel):
    id: str
    headline: str
    summary: str
    why_it_matters: str
    image_subject: str = ""  # main real-world subject to find a photo of, e.g. "Palo Alto Networks"


class Takeaway(BaseModel):
    text: str
    article_id: str


class ConnectTheDots(BaseModel):
    text: str
    article_ids: list[str]


class MindVitamin(BaseModel):
    title: str
    content: str


class SectionPhoto(BaseModel):
    topic: str
    wikipedia_title: str  # article whose photo best represents the section, e.g. "Spaceflight"


class QuizQuestion(BaseModel):
    question: str
    options: list[str] = Field(min_length=3, max_length=3)
    answer_index: int = Field(ge=0, le=2)
    article_id: str


class EditorOutput(BaseModel):
    articles: list[ArticleCopy]
    three_takeaways: list[Takeaway] = Field(min_length=3, max_length=3)
    connect_the_dots: ConnectTheDots
    mind_vitamin: MindVitamin
    recall_quiz: list[QuizQuestion] = Field(min_length=3, max_length=6)
    section_photos: list[SectionPhoto] = []  # optional: helps find a good topic photo


class InvalidOutput(ValueError):
    pass


# ---------- model call ----------

def _api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip()


def ai_available() -> bool:
    return bool(_api_key())


def call_llm(prompt: str) -> str:
    """Send one prompt to Gemini and return the raw JSON text. Tests replace this."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_api_key())
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_json_schema=EditorOutput.model_json_schema(),
            temperature=0.4,
        ),
    )
    return response.text or ""


def build_prompt(articles: list[dict], bio: str, topic_weights: dict) -> str:
    payload = {
        "reader": {"bio": bio, "topic_weights": topic_weights},
        "articles": [
            {
                "id": a["id"],
                "topic": a["topic"],
                "part": a.get("part", 1),
                "headline": a["headline"],
                "source": a["source_name"],
                "text": a.get("text", ""),
            }
            for a in articles
        ],
    }
    return "Write today's paper from these articles.\n" + json.dumps(payload, ensure_ascii=False, indent=2)


# ---------- validation ----------

def parse_output(raw: str, article_ids: set[str]) -> EditorOutput:
    """Parse and check the model's JSON. Raises InvalidOutput if anything is off."""
    try:
        output = EditorOutput.model_validate_json(raw)
    except ValidationError as exc:
        raise InvalidOutput(f"schema: {exc.error_count()} errors") from exc

    returned = [a.id for a in output.articles]
    if set(returned) != article_ids or len(returned) != len(article_ids):
        raise InvalidOutput("articles do not match the given ids")
    cited = [t.article_id for t in output.three_takeaways] + [q.article_id for q in output.recall_quiz]
    cited += output.connect_the_dots.article_ids
    unknown = set(cited) - article_ids
    if unknown:
        raise InvalidOutput(f"unknown article ids cited: {sorted(unknown)}")
    if any(not a.summary.strip() or not a.headline.strip() for a in output.articles):
        raise InvalidOutput("empty headline or summary")
    return output


# ---------- fallback ----------

MIND_VITAMINS = [
    ("One thing at a time", "Pick the one task that would make today feel finished, and do it before anything else."),
    ("Read slowly", "Understanding one story well beats skimming ten. Notice one idea today you could explain to a friend."),
    ("Leave a margin", "Plan for less than you can do. The space you leave is where good thinking happens."),
]


def _source_questions(articles: list[dict], part: int, count: int, skip: set[str] = frozenset()) -> list[QuizQuestion]:
    """No-AI Brain-check questions for one part: which outlet reported this headline?"""
    sources = list(dict.fromkeys(a["source_name"] for a in articles if a["source_name"]))
    pool = [a for a in articles if a.get("part", 1) == part and a["id"] not in skip][:count]
    questions = []
    for i, a in enumerate(pool):
        others = [s for s in sources if s != a["source_name"]][:2]
        others += ["A wire service", "A local paper"][: 2 - len(others)]
        options = others[:]
        answer_index = i % 3
        options.insert(answer_index, a["source_name"] or "Unknown source")
        questions.append(QuizQuestion(
            question=f"Which outlet reported: “{a['headline']}”?",
            options=options, answer_index=answer_index, article_id=a["id"],
        ))
    return questions


def complete_quiz(output: EditorOutput, articles: list[dict]) -> EditorOutput:
    """Make sure each part has its 3 Brain-check questions, topping up from the stories if the AI fell short."""
    part_of = {a["id"]: a.get("part", 1) for a in articles}
    quiz = []
    for part in sorted(set(part_of.values())):
        mine = [q for q in output.recall_quiz if part_of.get(q.article_id) == part][:3]
        if len(mine) < 3:
            mine += _source_questions(articles, part, 3 - len(mine), {q.article_id for q in mine})
        quiz += mine
    return output.model_copy(update={"recall_quiz": quiz[:6]})


def fallback_output(articles: list[dict]) -> EditorOutput:
    """Plain RSS text, no AI. Used when there is no key or the model fails twice."""
    copies = [
        ArticleCopy(
            id=a["id"],
            headline=a["headline"],
            # Google News gives no article text; point to the source rather than repeat the headline.
            summary=a.get("text") or f"Full story at {a['source_name'] or 'the source'}.",
            why_it_matters=f"In your paper because you follow {a['topic']}.",
        )
        for a in articles
    ]
    top = articles[:3]
    takeaways = [Takeaway(text=a["headline"], article_id=a["id"]) for a in top]

    quiz = [question for part in (1, 2) for question in _source_questions(articles, part, 3)]

    topics = list(dict.fromkeys(a["topic"] for a in articles))
    linked = [next(a["id"] for a in articles if a["topic"] == t) for t in topics[:2]]
    dots_text = (
        f"Today's paper runs from {topics[0]} to {topics[1]}. Read them side by side and look for the common thread."
        if len(topics) > 1 else f"Every story today is about {topics[0]}."
    )
    title, content = MIND_VITAMINS[len(articles) % len(MIND_VITAMINS)]
    return EditorOutput(
        articles=copies,
        three_takeaways=takeaways,
        connect_the_dots=ConnectTheDots(text=dots_text, article_ids=linked),
        mind_vitamin=MindVitamin(title=title, content=content),
        recall_quiz=quiz,
    )


# ---------- single story (Editor Desk swap) ----------

STORY_PROMPT = """Write copy for ONE replacement story in the reader's paper, using only facts in its text.
Return: article (same id, headline keeping the original meaning, 2-3 sentence summary, 1-sentence why_it_matters
for this reader), takeaway (one sentence the reader should remember, citing the same article_id), and
quiz (one question with 3 options, answer_index 0-2, answerable from your summary, citing the same article_id)."""


class StoryOutput(BaseModel):
    article: ArticleCopy
    takeaway: Takeaway
    quiz: QuizQuestion


def call_llm_story(prompt: str) -> str:
    """One Gemini call for a single story. Tests replace this."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_api_key())
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT + "\n\n" + STORY_PROMPT,
            response_mime_type="application/json",
            response_json_schema=StoryOutput.model_json_schema(),
            temperature=0.4,
        ),
    )
    return response.text or ""


def parse_story(raw: str, article_id: str) -> StoryOutput:
    try:
        out = StoryOutput.model_validate_json(raw)
    except ValidationError as exc:
        raise InvalidOutput(f"schema: {exc.error_count()} errors") from exc
    if {out.article.id, out.takeaway.article_id, out.quiz.article_id} != {article_id}:
        raise InvalidOutput("story output cites the wrong article id")
    if not out.article.summary.strip() or not out.article.headline.strip():
        raise InvalidOutput("empty headline or summary")
    return out


def fallback_story(article: dict, other_sources: list[str]) -> StoryOutput:
    others = [s for s in dict.fromkeys(other_sources) if s and s != article["source_name"]][:2]
    others += ["A wire service", "A local paper"][: 2 - len(others)]
    return StoryOutput(
        article=ArticleCopy(
            id=article["id"],
            headline=article["headline"],
            summary=article.get("text") or f"Full story at {article['source_name'] or 'the source'}.",
            why_it_matters=f"Swapped in because you asked for {article['topic']}.",
        ),
        takeaway=Takeaway(text=article["headline"], article_id=article["id"]),
        quiz=QuizQuestion(
            question=f"Which outlet reported: “{article['headline']}”?",
            options=[article["source_name"] or "Unknown source", *others],
            answer_index=0,
            article_id=article["id"],
        ),
    )


def write_story(article: dict, bio: str, topic_weights: dict, other_sources: list[str]) -> tuple[StoryOutput, str]:
    """Copy for one swapped-in story: (output, "ai" | "fallback"). One call, one retry."""
    if not ai_available():
        return fallback_story(article, other_sources), "fallback"
    prompt = build_prompt([article], bio, topic_weights).replace(
        "Write today's paper from these articles.", "Write copy for this one story."
    )
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return parse_story(call_llm_story(prompt), article["id"]), "ai"
        except InvalidOutput as exc:
            log.warning("AI story attempt %d rejected: %s", attempt, exc)
        except Exception as exc:
            log.warning("AI story attempt %d failed: %s", attempt, exc)
    return fallback_story(article, other_sources), "fallback"


# ---------- entry point ----------

def write_edition(articles: list[dict], bio: str, topic_weights: dict) -> tuple[EditorOutput, str]:
    """Return (output, writer) where writer is "ai" or "fallback"."""
    if len(articles) < 3:
        raise ValueError("need at least 3 articles for a paper")
    if not ai_available():
        return fallback_output(articles), "fallback"

    ids = {a["id"] for a in articles}
    prompt = build_prompt(articles, bio, topic_weights)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return complete_quiz(parse_output(call_llm(prompt), ids), articles), "ai"
        except InvalidOutput as exc:
            log.warning("AI editor attempt %d rejected: %s", attempt, exc)
        except Exception as exc:  # network, quota, SDK errors
            log.warning("AI editor attempt %d failed: %s", attempt, exc)
    return fallback_output(articles), "fallback"
