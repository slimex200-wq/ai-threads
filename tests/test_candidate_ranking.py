from datetime import datetime, timezone

from candidate_ranking import score_candidate


def test_recent_product_update_beats_evergreen_explainer():
    now = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    recent_update = {
        "title": "Google launches Gemini CLI for developers",
        "summary": "Google released Gemini CLI and opened access to developers.",
        "source": "Google Blog",
        "date": "2026-04-13",
        "engagement": 1200,
    }
    evergreen_explainer = {
        "title": "What Is Llama.cpp? The LLM Inference Engine for Local AI",
        "summary": "Explainer video about llama.cpp",
        "source": "YouTube/IBM Technology",
        "date": "2026-04-12",
        "engagement": 116097,
    }

    assert score_candidate(recent_update, now=now) > score_candidate(evergreen_explainer, now=now)


def test_polymarket_prediction_gets_penalized():
    now = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    prediction = {
        "title": "OpenAI announces it has achieved AGI before 2027?",
        "summary": "Prediction market on AGI.",
        "source": "Polymarket",
        "date": "2026-04-13",
        "engagement": 0,
    }
    practical_news = {
        "title": "Anthropic ships new Claude Code memory controls",
        "summary": "New controls for project memory in Claude Code.",
        "source": "TechCrunch",
        "date": "2026-04-13",
        "engagement": 500,
    }

    assert score_candidate(practical_news, now=now) > score_candidate(prediction, now=now)


def test_polymarket_question_market_gets_heavily_penalized_even_with_model_keyword():
    now = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    prediction = {
        "title": "Which company has the best AI model end of April?",
        "summary": "Prediction market that will resolve later.",
        "source": "Polymarket",
        "date": "2026-04-13",
        "engagement": 0,
    }
    release_news = {
        "title": "Alibaba releases Qwen update for local deployment",
        "summary": "New open-source model update with local deployment improvements.",
        "source": "AI Times",
        "date": "2026-04-13",
        "engagement": 50,
    }

    assert score_candidate(release_news, now=now) > score_candidate(prediction, now=now)
