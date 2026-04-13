import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from config import RSS_FEEDS

MAX_AGE_HOURS = 36  # 최대 36시간 이내 기사만 수집


def _parse_published(entry) -> datetime | None:
    """RSS entry에서 발행 시각을 UTC datetime으로 파싱."""
    # 1차: feedparser의 published_parsed (struct_time)
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except Exception:
            pass

    # 2차: 문자열 직접 파싱 (RFC 2822)
    raw = entry.get("published", "") or entry.get("updated", "")
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass

    return None


def collect_news(feeds=None, max_count=50, max_age_hours=MAX_AGE_HOURS):
    feeds = feeds or RSS_FEEDS
    now = datetime.now(timezone.utc)
    all_articles = []

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                pub_dt = _parse_published(entry)

                # 날짜 파싱 실패 시 제외 (오래된 기사 유입 방지)
                if not pub_dt:
                    continue
                age_hours = (now - pub_dt).total_seconds() / 3600
                if age_hours > max_age_hours:
                    continue
                pub_ts = pub_dt.timestamp()

                article = {
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "link": entry.get("link", ""),
                    "source": feed.feed.get("title", feed_url),
                    "published": entry.get("published", ""),
                    "date": pub_dt.strftime("%Y-%m-%d"),
                    "_pub_ts": pub_ts,
                }
                all_articles.append(article)
        except Exception as e:
            print(f"[경고] RSS 수집 실패 ({feed_url}): {e}")
            continue

    # 최신순 정렬
    all_articles.sort(key=lambda a: a["_pub_ts"], reverse=True)

    # 중복 제거 (정규화 제목 기준)
    from history import normalize_title
    seen = set()
    unique = []
    for a in all_articles:
        key = normalize_title(a["title"])
        if key not in seen:
            seen.add(key)
            unique.append(a)

    # 내부 정렬 키 제거
    for a in unique:
        a.pop("_pub_ts", None)

    return unique[:max_count]
