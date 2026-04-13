import os

# RSS 소스 (보충용)
RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://www.technologyreview.com/feed/",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://openai.com/blog/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://huggingface.co/blog/feed.xml",
    "https://www.aitimes.com/rss/allArticle.xml",
    "https://zdnet.co.kr/rss/ai_news.xml",
]

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"
THREADS_LLM_BACKEND = os.environ.get("THREADS_LLM_BACKEND", "claude_cli")  # claude_cli | anthropic_api | codex_cli | auto

# Threads API
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID", "")

# Telegram 알림
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Engagement tracking
ENGAGEMENT_WEIGHTS = {"views": 0.1, "likes": 5, "replies": 10, "reposts": 8, "quotes": 8}
ENGAGEMENT_DAYS = 7  # collect insights for posts within this many days

# Smart scheduler
MAX_DAILY_POSTS = 4
FORCE_POST_HOUR = 22  # KST hour — force at least 1 post if 0 today

# AI 키워드 필터링
AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "neural network", "llm", "large language model", "gpt", "claude",
    "gemini", "chatbot", "generative ai", "transformer", "diffusion",
    "reinforcement learning", "computer vision", "nlp",
    "natural language processing", "openai", "anthropic", "hugging face",
    "인공지능", "머신러닝", "딥러닝", "생성형", "대규모 언어 모델",
    "챗봇", "자연어 처리", "컴퓨터 비전", "강화학습",
]

# Content mode
CONTENT_MODE = os.environ.get("CONTENT_MODE", "informational")  # "viral" or "informational"

# API timing guardrails
PIPELINE_TIMEOUT = 300    # 전체 파이프라인 5분 제한
API_MAX_RETRIES = 3       # API 호출당 최대 재시도
API_RETRY_DELAY = 5       # 재시도 간격 (초)
