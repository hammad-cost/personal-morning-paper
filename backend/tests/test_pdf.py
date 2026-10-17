from io import BytesIO

import pytest
from pypdf import PdfReader

from app import pdf, store


def make_edition(n_articles=8, summary_words=40):
    topics = ["AI Agents", "Cybersecurity", "Space", "World News"]
    articles = [
        {
            "id": f"a{i}", "topic": topics[i % 4], "headline": f"Headline number {i} about {topics[i % 4]}",
            "summary": " ".join(["Calm"] + ["words"] * summary_words) + ".",
            "why_it_matters": "It matters to you.", "source_name": f"Outlet {i}", "url": f"https://news.test/story/{i}",
            "is_lead": i == 1, "is_explore": i == n_articles, "label": "Something new" if i == n_articles else None,
            "skipped": False, "clicked": False,
        }
        for i in range(1, n_articles + 1)
    ]
    articles[2]["skipped"] = True  # a3
    articles[2]["headline"] = "Skipped celebrity gossip story"
    return {
        "id": "ed-2026-10-17-2", "edition_number": 2, "date": "2026-10-17", "reading_minutes": 4,
        "three_takeaways": [{"text": f"Takeaway {i} – “quoted” & <marked>", "article_id": f"a{i}"} for i in (1, 2, 4)],
        "connect_the_dots": {"text": "These two stories connect.", "article_ids": ["a1", "a2"]},
        "mind_vitamin": {"title": "Read slowly", "content": "One idea, understood well."},
        "recall_quiz": [], "sections": topics, "articles": articles,
    }


def text_of(data: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)


def links_of(data: bytes) -> list[str]:
    uris = []
    for page in PdfReader(BytesIO(data)).pages:
        for annot in page.get("/Annots") or []:
            action = annot.get_object().get("/A")
            if action and action.get("/URI"):
                uris.append(action["/URI"])
    return uris


def test_builds_a_pdf_with_masthead_edition_number_and_takeaways():
    data = pdf.build_pdf(make_edition(), "The Ayesha Chronicle")
    assert data.startswith(b"%PDF")
    text = text_of(data)
    assert "THE AYESHA CHRONICLE" in text
    assert "EDITION NO. 2" in text
    assert "SATURDAY, OCTOBER 17, 2026" in text
    assert "3 THINGS YOU LEARNED TODAY" in text
    assert "Takeaway 1" in text and "&" in text  # markup characters are escaped, not dropped
    assert "Connect the Dots" in text and "Read slowly" in text
    assert "Printed by Vale" in " ".join(text.split())  # the footer may wrap


def test_skipped_stories_are_left_out():
    text = text_of(pdf.build_pdf(make_edition(), "The Ayesha Chronicle"))
    assert "Headline number 1" in text  # columns wrap the rest of the line
    assert "Skipped celebrity gossip story" not in text


def test_headlines_and_takeaways_are_live_links():
    links = links_of(pdf.build_pdf(make_edition(), "The Ayesha Chronicle"))
    assert "https://news.test/story/1" in links
    assert "https://news.test/story/3" not in links  # skipped
    assert links.count("https://news.test/story/2") >= 2  # headline + "Read original" (+ takeaway)


def test_reading_order_matches_the_web_page():
    order = [a["id"] for a in pdf.reading_order(make_edition())]
    assert order[0] == "a1"  # lead first
    assert "a3" not in order
    # a1..a8 cycle Cyber, Space, World, AI; sections print AI, Cyber, Space, World.
    assert order[1:] == ["a4", "a8", "a5", "a2", "a6", "a7"]


def test_long_editions_flow_onto_more_pages():
    data = pdf.build_pdf(make_edition(n_articles=10, summary_words=160), "The Ayesha Chronicle")
    assert len(PdfReader(BytesIO(data)).pages) >= 2


def test_filename():
    assert pdf.filename_for({"edition_number": 2}, "THE AYESHA CHRONICLE") == "the-ayesha-chronicle-edition-2.pdf"


# ---------- API ----------

def test_pdf_api(client):
    store.update(lambda d: (d["user"].update(paper_title="THE AYESHA CHRONICLE"), d["editions"].append(make_edition())))
    response = client.get("/api/edition/ed-2026-10-17-2/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert 'filename="the-ayesha-chronicle-edition-2.pdf"' in response.headers["content-disposition"]
    assert "Skipped celebrity gossip story" not in text_of(response.content)
    assert client.get("/api/edition/ed-nope/pdf").status_code == 404
