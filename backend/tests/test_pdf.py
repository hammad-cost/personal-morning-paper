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


def test_builds_a_newspaper_with_a_branded_cover():
    data = pdf.build_pdf(make_edition(), "The Ayesha Chronicle", weights={"AI Agents": 12, "Space": 4, "Sport": -3}, reader="Ayesha")
    assert data.startswith(b"%PDF")
    cover = " ".join(PdfReader(BytesIO(data)).pages[0].extract_text().split())
    assert "Vale" in cover and "One calm paper a day" in cover
    assert "PRINTED FOR AYESHA BY VALE" in cover
    assert "THE AYESHA CHRONICLE" in cover
    assert "EDITION NO. 2" in cover and "SATURDAY, OCTOBER 17, 2026" in cover
    assert "TODAY'S LEAD STORY" in cover and "Headline number 1" in cover
    assert "INSIDE TODAY" in cover
    assert "WHAT VALE HAS LEARNED ABOUT YOU" in cover and "AI Agents" in cover
    text = " ".join(text_of(data).split())
    # A newspaper, not a study sheet.
    for gone in ["3 THINGS YOU LEARNED TODAY", "Takeaway 1", "BRAIN CHECK", "Connect the Dots", "Read slowly"]:
        assert gone not in text
    assert "Printed by Vale" in text


def test_cover_index_lists_every_other_story_with_its_page():
    ed = make_edition(n_articles=10, summary_words=120)
    data = pdf.build_pdf(ed, "T")
    reader = PdfReader(BytesIO(data))
    cover = " ".join(reader.pages[0].extract_text().split())
    for a in pdf.reading_order(ed)[1:]:
        page = next(i for i, p in enumerate(reader.pages, start=1) if a["headline"] in " ".join(p.extract_text().split()) and i > 1)
        assert f"{a['headline']} p.{page}" in cover


def test_interests_chart_shows_strongest_positive_topics_only():
    assert pdf.interest_rows({"AI": 10, "Space": 3, "Sport": -4, "Cats": 0}) == [("AI", 10), ("Space", 3)]
    text = text_of(pdf.build_pdf(make_edition(), "T", weights={}))
    assert "WHAT VALE HAS LEARNED" not in text  # nothing learned yet, no empty chart


def test_text_the_pdf_fonts_cannot_draw_is_dropped_not_boxed():
    ed = make_edition()
    ed["articles"][1]["source_name"] = "दैनिक"  # Hindi: no glyphs in the PDF fonts
    ed["articles"][1]["url"] = "https://www.bhaskar.com/news/1"
    text = " ".join(text_of(pdf.build_pdf(ed, "T")).split())
    assert "bhaskar.com" in text and "■" not in text
    assert pdf._plain("Café “quoted” – दै") == "Café “quoted” –"


def test_skipped_stories_are_left_out():
    text = text_of(pdf.build_pdf(make_edition(), "The Ayesha Chronicle"))
    assert "Headline number 1" in text  # columns wrap the rest of the line
    assert "Skipped celebrity gossip story" not in text


def test_headlines_and_citations_are_live_links():
    links = links_of(pdf.build_pdf(make_edition(), "The Ayesha Chronicle"))
    assert "https://news.test/story/1" in links
    assert "https://news.test/story/3" not in links  # skipped
    assert links.count("https://news.test/story/2") >= 2  # headline + citation link


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


# ---------- printed paper extras: QR codes, parts, Brain check ----------

def test_every_printed_story_has_a_qr_and_citation():
    ed = make_edition()
    text = " ".join(text_of(pdf.build_pdf(ed, "The Ayesha Chronicle")).split())
    printed = [a for a in ed["articles"] if not a["skipped"]]
    assert text.count("Scan for the original") == len(printed)
    assert "news.test/story/1" in text  # the printed short link


def test_qr_codes_hold_the_original_article_link():
    article = {"url": "https://news.google.com/rss/articles/x", "publisher_url": "https://www.reuters.com/tech/ai-story"}
    qr = pdf._qr(pdf.link_of(article))
    assert qr.contents[0].value == "https://www.reuters.com/tech/ai-story"  # straight to the publisher
    assert qr.width == qr.height == pdf.QR_SIZE


def test_short_links_read_well_in_print():
    assert pdf.short_link("https://www.reuters.com/technology/") == "reuters.com/technology"
    long = pdf.short_link("https://example.com/" + "a" * 80)
    assert long.endswith("…") and len(long) == 38


def test_part_two_banner_and_no_printed_quiz():
    ed = make_edition(n_articles=8)
    for a in ed["articles"][4:]:
        a["part"] = 2
    ed["recall_quiz"] = [{"question": "Which outlet?", "options": ["One", "Two", "Three"], "answer_index": 1, "article_id": "a1"}]
    text = " ".join(text_of(pdf.build_pdf(ed, "T")).split())
    assert "MORE FOR YOU · PART 2" in text
    assert "Which outlet?" not in text and "BRAIN CHECK" not in text


def test_qr_codes_are_coarse_enough_for_a_phone_camera():
    # Each square must stay around 0.5 mm or more on paper for a typical publisher link.
    url = "https://www.reuters.com/technology/artificial-intelligence/rogue-ai-agents-break-into-live-systems-2026-10-17/?utm_source=x&utm_medium=rss"
    qr = pdf._qr(url)
    widget = qr.contents[0]
    widget.getBounds()
    modules = len(widget.qr.modules) + 2 * widget.barBorder
    module_mm = pdf.QR_SIZE / 72 * 25.4 / modules
    assert module_mm >= 0.5
    assert widget.value == "https://www.reuters.com/technology/artificial-intelligence/rogue-ai-agents-break-into-live-systems-2026-10-17/"


def test_qr_target_strips_tracking_but_keeps_real_parameters():
    assert pdf.qr_target("https://a.test/story?id=7&utm_campaign=x&fbclid=y#top") == "https://a.test/story?id=7"
    assert pdf.qr_target("https://news.google.com/rss/articles/ABC?oc=5&hl=en-US") == "https://news.google.com/rss/articles/ABC"
