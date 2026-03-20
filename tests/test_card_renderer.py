import sys
sys.path.insert(0, '.')
import os
import tempfile
from pathlib import Path
from card_renderer import render_cover, render_news_card, render_closing

def test_render_cover_creates_image():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = render_cover("AI Weekly", "2026-03-20", Path(tmpdir))
        assert os.path.exists(path)
        assert path.endswith(".png")

def test_render_news_card_creates_image():
    card_data = {
        "number": 1,
        "title": "테스트 뉴스 제목",
        "subtitle": "AI가 새로운 것을 합니다",
        "points": ["핵심 포인트 1", "핵심 포인트 2"],
        "source": "TechCrunch"
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        path = render_news_card(card_data, 2, Path(tmpdir))
        assert os.path.exists(path)

def test_render_closing_creates_image():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = render_closing("읽어주셔서 감사합니다", 5, Path(tmpdir))
        assert os.path.exists(path)
