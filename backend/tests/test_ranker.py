from datetime import datetime, timedelta, timezone

from app import ranker

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
WEIGHTS = {"AI Agents": 12, "Cybersecurity": 10, "Space": 5, "Crypto": -10}


def art(id, topic, hours_ago=30, source=None, url=None):
    published = (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": id, "topic": topic, "headline": f"Story {id}", "text": "",
        "source_name": source or f"Wire {id}", "url": url or f"https://news.test/{id}",
        "published_at": published,
    }


def test_score_formula():
    a = art("x", "AI Agents", hours_ago=2, source="TechCrunch", url="https://seen.test/x")
    assert ranker.score_article(a, WEIGHTS, {}, set(), NOW) == 12 + 3
    assert ranker.score_article(a, WEIGHTS, {"TechCrunch": 2}, set(), NOW) == 12 + 3 + 2
    assert ranker.score_article(a, WEIGHTS, {}, {"https://seen.test/x"}, NOW) == 12 + 3 - 10
    assert ranker.recency_bonus(art("y", "Space", hours_ago=18)["published_at"], NOW) == 1.5
    assert ranker.recency_bonus(art("z", "Space", hours_ago=30)["published_at"], NOW) == 0
    # Unknown topics count as weight 0.
    assert ranker.score_article(art("n", "World News"), WEIGHTS, {}, set(), NOW) == 0


def test_bare_domain_sources_lose_ties_to_real_outlets():
    assert ranker.is_bare_domain("kpmg.com")
    assert ranker.is_bare_domain("marketscreener.com")
    assert not ranker.is_bare_domain("Reuters")
    assert not ranker.is_bare_domain("Cybersecurity Dive")
    brochure = art("k", "Cybersecurity", hours_ago=1, source="kpmg.com")
    news = art("n", "Cybersecurity", hours_ago=3, source="CyberScoop")
    assert ranker.score_article(brochure, WEIGHTS, {}, set(), NOW) == 10 + 3 - 1
    paper = ranker.rank([brochure, news], WEIGHTS, now=NOW)
    assert paper["articles"][0]["id"] == "n"


def many_candidates():
    return (
        [art(f"ai{i}", "AI Agents", hours_ago=i) for i in range(6)]
        + [art(f"cy{i}", "Cybersecurity", hours_ago=i) for i in range(6)]
        + [art(f"sp{i}", "Space", hours_ago=i) for i in range(6)]
        + [art("w1", "World News", hours_ago=1), art("cr1", "Crypto", hours_ago=1)]
    )


def test_rank_picks_ten_with_lead_cap_and_one_explore():
    paper = ranker.rank(many_candidates(), WEIGHTS, now=NOW)
    articles = paper["articles"]
    assert len(articles) == 10

    # The top score leads and comes first.
    lead = articles[0]
    assert lead["is_lead"] and lead["id"] == "ai0"
    assert sum(a["is_lead"] for a in articles) == 1
    assert lead["score"] == max(a["score"] for a in articles)

    # At most 3 per topic.
    topics = [a["topic"] for a in articles]
    assert all(topics.count(t) <= 3 for t in set(topics))

    # Exactly one explore story, from a low or new topic not already in the paper, labelled.
    explore = [a for a in articles if a["is_explore"]]
    assert len(explore) == 1
    assert explore[0]["topic"] == "World News"
    assert explore[0]["label"] == "Something new"


def test_blocked_topics_never_appear():
    paper = ranker.rank(many_candidates(), WEIGHTS, now=NOW)
    assert "Crypto" not in {a["topic"] for a in paper["articles"]}
    assert "Crypto" not in paper["sections"]


def test_sections_follow_topic_weight_and_articles_follow_sections():
    paper = ranker.rank(many_candidates(), WEIGHTS, now=NOW)
    assert paper["sections"] == ["AI Agents", "Cybersecurity", "Space", "World News"]
    rest = paper["articles"][1:]
    order = [paper["sections"].index(a["topic"]) for a in rest]
    assert order == sorted(order)


def test_one_story_per_source_in_each_section():
    candidates = [
        art("k1", "Cybersecurity", hours_ago=1, source="kpmg.com"),
        art("k2", "Cybersecurity", hours_ago=1, source="kpmg.com"),
        art("k3", "Cybersecurity", hours_ago=1, source="kpmg.com"),
        art("c1", "Cybersecurity", hours_ago=2, source="CyberScoop"),
        art("a1", "AI Agents", hours_ago=2, source="kpmg.com"),
    ]
    paper = ranker.rank(candidates, WEIGHTS, now=NOW)
    cyber = [a for a in paper["articles"] if a["topic"] == "Cybersecurity"]
    assert [a["source_name"] for a in cyber].count("kpmg.com") == 1
    assert "c1" in {a["id"] for a in cyber}
    # The same source may still appear in a different section.
    assert "a1" in {a["id"] for a in paper["articles"]}


def test_seen_urls_push_stories_down():
    candidates = [art("old", "AI Agents", hours_ago=1), art("new", "AI Agents", hours_ago=20)]
    paper = ranker.rank(candidates, WEIGHTS, seen_urls={"https://news.test/old"}, now=NOW)
    assert paper["articles"][0]["id"] == "new"


def test_explore_falls_back_to_a_low_weight_reader_topic():
    candidates = (
        [art(f"ai{i}", "AI Agents", hours_ago=i) for i in range(3)]
        + [art(f"cy{i}", "Cybersecurity", hours_ago=i) for i in range(3)]
        + [art("sp0", "Space", hours_ago=1)]
    )
    paper = ranker.rank(candidates, WEIGHTS, now=NOW)
    explore = [a for a in paper["articles"] if a["is_explore"]]
    # Only 7 candidates: all are used, and Space (weight 5) is the explore pick.
    assert len(paper["articles"]) == 7
    assert [a["id"] for a in explore] == ["sp0"]


def test_rank_handles_few_or_no_candidates():
    assert ranker.rank([], WEIGHTS, now=NOW) == {"articles": [], "sections": []}
    paper = ranker.rank([art("one", "Space")], WEIGHTS, now=NOW)
    assert len(paper["articles"]) == 1
    assert paper["articles"][0]["is_lead"]
