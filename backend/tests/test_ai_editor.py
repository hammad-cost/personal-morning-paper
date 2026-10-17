import json

import pytest

from app import ai_editor

ARTICLES = [
    {"id": f"a{i}", "topic": t, "headline": f"Headline {i}", "source_name": s, "text": f"Text {i}.",
     "url": f"https://news.test/{i}"}
    for i, (t, s) in enumerate(
        [("AI Agents", "Reuters"), ("Cybersecurity", "CyberScoop"), ("Space", "BBC News"), ("AI Agents", "TechCrunch")],
        start=1,
    )
]
IDS = {a["id"] for a in ARTICLES}


def valid_output(**overrides) -> dict:
    out = {
        "articles": [
            {"id": a["id"], "headline": a["headline"], "summary": "Two calm sentences. Facts only.",
             "why_it_matters": "It matters to you."}
            for a in ARTICLES
        ],
        "three_takeaways": [{"text": f"Takeaway {i}", "article_id": f"a{i}"} for i in (1, 2, 3)],
        "connect_the_dots": {"text": "These connect.", "article_ids": ["a1", "a4"]},
        "mind_vitamin": {"title": "Breathe", "content": "Slow down."},
        "recall_quiz": [
            {"question": f"Q{i}?", "options": ["x", "y", "z"], "answer_index": 1, "article_id": f"a{i}"}
            for i in (1, 2, 3)
        ],
    }
    out.update(overrides)
    return out


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


def fake_llm(monkeypatch, *replies):
    calls = []
    replies = list(replies)

    def call(prompt):
        calls.append(prompt)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(ai_editor, "call_llm", call)
    return calls


def test_valid_ai_response_parses(with_key, monkeypatch):
    calls = fake_llm(monkeypatch, json.dumps(valid_output()))
    output, writer = ai_editor.write_edition(ARTICLES, "CS student", {"AI Agents": 10})
    assert writer == "ai"
    assert len(calls) == 1
    assert output.articles[0].summary == "Two calm sentences. Facts only."
    assert [t.article_id for t in output.three_takeaways] == ["a1", "a2", "a3"]
    # The prompt carries the reader and only the fetched text.
    prompt = json.loads(calls[0].split("\n", 1)[1])
    assert prompt["reader"]["bio"] == "CS student"
    assert prompt["articles"][0] == {"id": "a1", "topic": "AI Agents", "part": 1, "headline": "Headline 1",
                                     "source": "Reuters", "text": "Text 1."}


def test_invalid_json_retries_then_falls_back(with_key, monkeypatch):
    calls = fake_llm(monkeypatch, "not json", '{"articles": []}')
    output, writer = ai_editor.write_edition(ARTICLES, "", {})
    assert len(calls) == 2
    assert writer == "fallback"
    assert output.articles[0].summary == "Text 1."


def test_retry_succeeds_after_one_bad_reply(with_key, monkeypatch):
    calls = fake_llm(monkeypatch, "oops", json.dumps(valid_output()))
    _, writer = ai_editor.write_edition(ARTICLES, "", {})
    assert len(calls) == 2
    assert writer == "ai"


def test_api_errors_count_as_failures(with_key, monkeypatch):
    calls = fake_llm(monkeypatch, RuntimeError("quota"), RuntimeError("quota"))
    _, writer = ai_editor.write_edition(ARTICLES, "", {})
    assert len(calls) == 2
    assert writer == "fallback"


@pytest.mark.parametrize("bad", [
    {"three_takeaways": [{"text": "x", "article_id": "a99"}] * 3},
    {"connect_the_dots": {"text": "x", "article_ids": ["a1", "zz"]}},
    {"articles": valid_output()["articles"][:3]},
    {"recall_quiz": [{"question": "q", "options": ["x", "y"], "answer_index": 0, "article_id": "a1"}] * 3},
    {"recall_quiz": [{"question": "q", "options": ["x", "y", "z"], "answer_index": 5, "article_id": "a1"}] * 3},
])
def test_rejects_output_that_cites_unknown_ids_or_breaks_schema(bad):
    with pytest.raises(ai_editor.InvalidOutput):
        ai_editor.parse_output(json.dumps(valid_output(**bad)), IDS)


def test_no_key_skips_the_ai_entirely(monkeypatch):
    # conftest removes GEMINI_API_KEY and makes call_llm raise if it is ever used.
    output, writer = ai_editor.write_edition(ARTICLES, "", {})
    assert writer == "fallback"
    assert len(output.articles) == 4


def test_fallback_takeaways_and_quiz_reference_real_articles():
    output = ai_editor.fallback_output(ARTICLES)
    assert len(output.three_takeaways) == 3
    assert len(output.recall_quiz) == 3
    cited = [t.article_id for t in output.three_takeaways] + [q.article_id for q in output.recall_quiz]
    cited += output.connect_the_dots.article_ids
    assert set(cited) <= IDS
    for q, a in zip(output.recall_quiz, ARTICLES):
        assert len(q.options) == 3
        assert q.options[q.answer_index] == a["source_name"]
    # The fallback must itself pass the same checks as an AI reply.
    ai_editor.parse_output(output.model_dump_json(), IDS)


def test_fallback_never_repeats_the_headline_as_summary():
    bare = [{**a, "text": ""} for a in ARTICLES]
    output = ai_editor.fallback_output(bare)
    assert output.articles[0].summary == "Full story at Reuters."


def test_needs_at_least_three_articles():
    with pytest.raises(ValueError):
        ai_editor.write_edition(ARTICLES[:2], "", {})


def test_each_part_gets_three_brain_check_questions():
    arts = [{"id": f"a{i}", "topic": "AI", "headline": f"H{i}", "source_name": f"S{i}", "text": "", "part": 1 if i <= 4 else 2}
            for i in range(1, 9)]
    short = ai_editor.EditorOutput.model_validate(valid_output(
        articles=[{"id": a["id"], "headline": a["headline"], "summary": "S.", "why_it_matters": "W."} for a in arts],
        recall_quiz=[{"question": f"Q{i}?", "options": ["x", "y", "z"], "answer_index": 0, "article_id": f"a{i}"} for i in (1, 2, 3)],
    ))
    quiz = ai_editor.complete_quiz(short, arts).recall_quiz
    part_of = {a["id"]: a["part"] for a in arts}
    assert [part_of[q.article_id] for q in quiz] == [1, 1, 1, 2, 2, 2]  # part 2 topped up from the stories
    fallback = ai_editor.fallback_output(arts).recall_quiz
    assert [part_of[q.article_id] for q in fallback] == [1, 1, 1, 2, 2, 2]
