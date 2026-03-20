import feedparser
from config import RSS_FEEDS

def collect_news(feeds=None, max_count=4):
    feeds = feeds or RSS_FEEDS
    all_articles = []

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                article = {
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "link": entry.get("link", ""),
                    "source": feed.feed.get("title", feed_url),
                    "published": entry.get("published", ""),
                }
                all_articles.append(article)
        except Exception as e:
            print(f"[경고] RSS 수집 실패 ({feed_url}): {e}")
            continue

    # 중복 제거 (제목 기준)
    seen = set()
    unique = []
    for a in all_articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    return unique[:max_count]
