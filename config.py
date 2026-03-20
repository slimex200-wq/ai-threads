import os
from pathlib import Path
from datetime import date

# RSS 소스
RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://www.technologyreview.com/feed/",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
]

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"

# 카드 디자인
CARD_WIDTH = 1080
CARD_HEIGHT = 1080
BG_COLOR = "#FFFFFF"
TEXT_COLOR = "#1A1A1A"
ACCENT_COLOR = "#2563EB"
SUB_TEXT_COLOR = "#6B7280"
FONT_PATH = "C:/Windows/Fonts/malgunbd.ttf"
FONT_PATH_REGULAR = "C:/Windows/Fonts/malgun.ttf"

# 출력
DEFAULT_OUTPUT = Path.home() / "Desktop" / "ai-cardnews"
DEFAULT_COUNT = 4

def get_output_dir(custom_path=None):
    base = Path(custom_path) if custom_path else DEFAULT_OUTPUT
    today = date.today().isoformat()
    output = base / today
    output.mkdir(parents=True, exist_ok=True)
    return output
