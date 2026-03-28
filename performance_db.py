"""포스트 성과 데이터 저장/조회 — 자가학습 피드백 루프."""

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

PERFORMANCE_FILE = Path("output/performance.json")

# 주요 AI 기업 목록 (주제 다양성 추출용)
_KNOWN_COMPANIES = [
    "오픈AI", "OpenAI", "구글", "Google", "메타", "Meta", "애플", "Apple",
    "마이크로소프트", "MS", "Microsoft", "앤트로픽", "Anthropic", "xAI",
    "엔비디아", "NVIDIA", "Nvidia", "삼성", "Samsung", "테슬라", "Tesla",
    "아마존", "Amazon", "바이두", "Baidu", "미스트랄", "Mistral",
    "허깅페이스", "Hugging Face", "코히어", "Cohere", "사카나", "Sakana",
    "스태빌리티", "Stability", "딥시크", "DeepSeek",
]


def _load():
    if not PERFORMANCE_FILE.exists():
        return []
    try:
        return json.loads(PERFORMANCE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return []


def _save(data):
    PERFORMANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PERFORMANCE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _extract_company(title):
    """기사 제목에서 회사명 추출."""
    for company in _KNOWN_COMPANIES:
        if company.lower() in title.lower():
            return company
    return ""


def save_post(post_id, content, hour):
    """포스팅 직후 성과 DB에 기록."""
    data = _load()
    article = content.get("selected_article", {})
    entry = {
        "post_id": post_id,
        "date": date.today().isoformat(),
        "hour": hour,
        "topic_tag": content.get("topic_tag", ""),
        "company": _extract_company(article.get("original_title", "")),
        "article_title": article.get("original_title", ""),
        "post_main": content.get("post_main", ""),
        "reply_casual": content.get("reply_casual", ""),
        "insights_collected": False,
        "likes": 0,
        "replies": 0,
        "views": 0,
        "score": 0.0,
    }
    data.append(entry)
    # 30일 이상 된 데이터 정리
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    data = [e for e in data if e.get("date", "") >= cutoff]
    _save(data)


def get_pending_insights(min_age_hours=6):
    """인사이트 미수집 + 일정 시간 경과한 포스트 반환."""
    data = _load()
    cutoff = datetime.now() - timedelta(hours=min_age_hours)
    cutoff_date = cutoff.strftime("%Y-%m-%d")
    cutoff_hour = cutoff.hour
    pending = []
    for e in data:
        if e.get("insights_collected"):
            continue
        # 날짜가 오늘보다 이전이면 무조건 포함
        if e.get("date", "") < cutoff_date:
            pending.append(e)
        # 같은 날이면 시간 비교
        elif e.get("date", "") == cutoff_date and e.get("hour", 24) <= cutoff_hour:
            pending.append(e)
    return pending


def update_insights(post_id, likes, replies, views):
    """인사이트 수집 결과 업데이트."""
    data = _load()
    for e in data:
        if e.get("post_id") == post_id:
            e["likes"] = likes
            e["replies"] = replies
            e["views"] = views
            e["score"] = likes + (replies * 3) + (views * 0.01)
            e["insights_collected"] = True
            break
    _save(data)


def get_top_posts(n=3):
    """성과 상위 N개 포스트 반환."""
    data = _load()
    scored = [e for e in data if e.get("insights_collected")]
    scored.sort(key=lambda e: e.get("score", 0), reverse=True)
    return scored[:n]


def get_bottom_posts(n=2):
    """성과 하위 N개 포스트 반환."""
    data = _load()
    scored = [e for e in data if e.get("insights_collected")]
    scored.sort(key=lambda e: e.get("score", 0))
    return scored[:n]


def get_recent_topics(n=6):
    """최근 N개 포스트의 회사/주제 반환 (다양성 체크용)."""
    data = _load()
    data.sort(key=lambda e: (e.get("date", ""), e.get("hour", 0)), reverse=True)
    topics = []
    for e in data[:n]:
        topic = e.get("company") or e.get("topic_tag") or ""
        if topic and topic not in topics:
            topics.append(topic)
    return topics
