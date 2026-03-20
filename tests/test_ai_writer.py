import sys
sys.path.insert(0, '.')
import json
from ai_writer import build_prompt, parse_response

def test_build_prompt_contains_articles():
    articles = [
        {"title": "Test AI News", "summary": "AI does things", "source": "TechCrunch", "link": "https://example.com"}
    ]
    prompt = build_prompt(articles)
    assert "Test AI News" in prompt
    assert "AI does things" in prompt

def test_parse_response_extracts_cards():
    sample = json.dumps({
        "cover_title": "AI Weekly",
        "cover_date": "2026-03-20",
        "cards": [
            {
                "number": 1,
                "title": "테스트 뉴스",
                "subtitle": "AI가 새로운 것을 함",
                "points": ["포인트 1", "포인트 2"],
                "source": "TechCrunch"
            }
        ],
        "closing_message": "읽어주셔서 감사합니다"
    })
    result = parse_response(sample)
    assert result["cover_title"] == "AI Weekly"
    assert len(result["cards"]) == 1
    assert result["cards"][0]["title"] == "테스트 뉴스"
