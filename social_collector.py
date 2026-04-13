"""Cost-aware multi-source AI news collection.

This module uses the local `last30days` skill adapters, but does not blindly
re-fetch 30 days of data on every run.

Collection strategy:
- HOT sources: refresh every run with a short window for freshness
- WARM sources: refresh every few hours with a medium window
- COLD refresh: once per day, rebuild a 30-day source cache
- CACHE fallback: reuse stored 30-day source cache when a refresh is not needed

This preserves "recent 30-day awareness" without paying the full collection
cost on every execution.
"""

from __future__ import annotations

import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


_SKILL_LIB = Path.home() / ".claude" / "skills" / "last30days" / "scripts"
if _SKILL_LIB.exists() and str(_SKILL_LIB) not in sys.path:
    sys.path.insert(0, str(_SKILL_LIB))

OUTPUT_DIR = Path("output")
SOCIAL_CACHE_FILE = OUTPUT_DIR / "social_cache.json"

AI_TOPIC = "artificial intelligence AI LLM"

WINDOW_LOOKBACK_DAYS = {
    "hot": 1,
    "warm": 3,
    "cold": 30,
}

SOURCE_POLICIES: dict[str, dict[str, Any]] = {
    "HN": {"always_hot": True, "warm_refresh_hours": 6, "cold_refresh_hours": 24},
    "YouTube": {"always_hot": True, "warm_refresh_hours": 6, "cold_refresh_hours": 24},
    "Reddit": {"always_hot": False, "warm_refresh_hours": 6, "cold_refresh_hours": 24},
    "TikTok": {"always_hot": False, "warm_refresh_hours": 6, "cold_refresh_hours": 24},
    "Instagram": {"always_hot": False, "warm_refresh_hours": 6, "cold_refresh_hours": 24},
    "Bluesky": {"always_hot": False, "warm_refresh_hours": 6, "cold_refresh_hours": 24},
    "TruthSocial": {"always_hot": False, "warm_refresh_hours": 6, "cold_refresh_hours": 24},
    "Polymarket": {"always_hot": False, "warm_refresh_hours": 6, "cold_refresh_hours": 24},
}

SOURCE_LIMITS = {
    "Reddit": 15,
    "HN": 10,
    "YouTube": 8,
    "TikTok": 8,
    "Instagram": 8,
    "Bluesky": 8,
    "TruthSocial": 5,
    "Polymarket": 5,
}

SOURCE_CACHE_LIMITS = {name: max(limit * 4, 20) for name, limit in SOURCE_LIMITS.items()}


def _normalize(
    items: list[dict[str, Any]],
    source_name: str,
    *,
    title_key: str = "title",
    summary_key: str | None = None,
    link_key: str = "url",
    score_fn: Callable[[dict[str, Any]], int | float] | None = None,
    date_key: str = "date",
    fallback_date: str = "",
) -> list[dict[str, Any]]:
    """Convert last30days adapter results into our internal article format."""
    articles: list[dict[str, Any]] = []
    for item in items:
        title = item.get(title_key, "") or ""
        if not title:
            title = (item.get("text", "") or "")[:120]
        if not title:
            continue

        summary = item.get(summary_key, "") if summary_key else ""
        if not summary:
            summary = item.get("text", "") or item.get("selftext", "") or title
        summary = summary[:400]

        link = item.get(link_key, "") or item.get("hn_url", "") or ""
        author = item.get("author_name", "") or item.get("handle", "") or ""
        if author:
            label = f"{source_name}/@{author}"
        elif item.get("subreddit"):
            label = f"r/{item['subreddit']}"
        elif item.get("channel_name"):
            label = f"YouTube/{item['channel_name']}"
        else:
            label = source_name

        score = score_fn(item) if score_fn else 0
        articles.append(
            {
                "title": title,
                "summary": summary,
                "source": label,
                "link": link,
                "date": item.get(date_key, "") or fallback_date,
                "_score": score,
            }
        )
    return articles


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _load_social_cache(path: Path | None = None) -> dict[str, Any]:
    path = path or SOCIAL_CACHE_FILE
    if not path.exists():
        return {"sources": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"sources": {}}
    if "sources" not in data or not isinstance(data["sources"], dict):
        return {"sources": {}}
    return data


def _save_social_cache(cache: dict[str, Any], path: Path | None = None) -> None:
    path = path or SOCIAL_CACHE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _article_key(article: dict[str, Any]) -> str:
    from history import normalize_title

    link = str(article.get("link", "")).strip()
    if link:
        return f"url::{link}"
    return f"title::{normalize_title(article.get('title', ''))}"


def _article_sort_score(article: dict[str, Any], now: datetime) -> float:
    raw_score = float(article.get("_score", article.get("engagement", 0)) or 0)
    age_days = 999
    article_date = _parse_date(article.get("date", ""))
    if article_date:
        age_days = max(0, (now.date() - article_date).days)

    freshness_bonus = max(0.0, (30 - min(age_days, 30)) / 30)
    return freshness_bonus * 10 + math.log1p(max(0.0, raw_score))


def _determine_refresh_mode(source_name: str, entry: dict[str, Any] | None, now: datetime) -> str:
    policy = SOURCE_POLICIES[source_name]
    if not entry:
        return "cold"

    last_refresh = _parse_datetime(entry.get("last_refresh_at"))
    if last_refresh is None:
        return "cold"

    age_hours = (now - last_refresh).total_seconds() / 3600
    if age_hours >= policy["cold_refresh_hours"]:
        return "cold"
    if policy.get("always_hot"):
        return "hot"
    if age_hours >= policy["warm_refresh_hours"]:
        return "warm"
    return "cache"


def _build_date_window(mode: str, now: datetime) -> tuple[str, str]:
    lookback_days = WINDOW_LOOKBACK_DAYS[mode]
    from_date = (now.date() - timedelta(days=lookback_days)).isoformat()
    to_date = now.date().isoformat()
    return from_date, to_date


def _filter_articles_to_window(articles: list[dict[str, Any]], from_date: str) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for article in articles:
        article_date = article.get("date", "")
        if article_date and article_date < from_date:
            continue
        filtered.append(article)
    return filtered


def _merge_cached_items(
    existing: list[dict[str, Any]],
    fresh: list[dict[str, Any]],
    *,
    now: datetime,
    max_age_days: int = 30,
) -> list[dict[str, Any]]:
    cutoff_date = now.date() - timedelta(days=max_age_days)
    cutoff_dt = now - timedelta(days=max_age_days)
    merged: dict[str, dict[str, Any]] = {}

    for article in existing:
        item = dict(article)
        article_date = _parse_date(item.get("date", ""))
        cached_at = _parse_datetime(item.get("cached_at"))
        if article_date and article_date < cutoff_date:
            continue
        if not article_date and cached_at and cached_at < cutoff_dt:
            continue
        merged[_article_key(item)] = item

    for article in fresh:
        item = dict(article)
        item["cached_at"] = now.isoformat()
        merged[_article_key(item)] = item

    items = list(merged.values())
    items.sort(key=lambda article: _article_sort_score(article, now), reverse=True)
    return items


def _collect_reddit(from_date: str, to_date: str) -> list[dict[str, Any]]:
    try:
        from lib.reddit import search_reddit

        result = search_reddit(AI_TOPIC, from_date, to_date, depth="quick")
        items = result.get("items", [])
        return _normalize(
            items,
            "Reddit",
            score_fn=lambda item: item.get("engagement", {}).get("score", 0),
        )
    except Exception as exc:
        print(f"  [Reddit] failed: {exc}")
        return []


def _collect_hackernews(from_date: str, to_date: str) -> list[dict[str, Any]]:
    try:
        from lib.hackernews import search_hackernews

        result = search_hackernews(AI_TOPIC, from_date, to_date, depth="quick")
        items = result.get("hits", [])
        return _normalize(
            items,
            "HN",
            score_fn=lambda item: item.get("engagement", {}).get("points", 0),
        )
    except Exception as exc:
        print(f"  [HN] failed: {exc}")
        return []


def _collect_youtube(from_date: str, to_date: str) -> list[dict[str, Any]]:
    try:
        from lib.youtube_yt import is_ytdlp_installed, search_youtube

        if not is_ytdlp_installed():
            print("  [YouTube] yt-dlp missing, skipping")
            return []

        result = search_youtube(AI_TOPIC, from_date, to_date, depth="quick")
        items = result.get("items", [])
        return _normalize(
            items,
            "YouTube",
            link_key="url",
            score_fn=lambda item: item.get("engagement", {}).get("views", 0),
        )
    except Exception as exc:
        print(f"  [YouTube] failed: {exc}")
        return []


def _collect_tiktok(from_date: str, to_date: str) -> list[dict[str, Any]]:
    try:
        from lib.tiktok import search_tiktok

        result = search_tiktok(AI_TOPIC, from_date, to_date, depth="quick")
        items = result.get("items", [])
        return _normalize(
            items,
            "TikTok",
            title_key="text",
            score_fn=lambda item: item.get("engagement", {}).get("views", 0),
        )
    except Exception as exc:
        print(f"  [TikTok] failed: {exc}")
        return []


def _collect_instagram(from_date: str, to_date: str) -> list[dict[str, Any]]:
    try:
        from lib.instagram import search_instagram

        result = search_instagram(AI_TOPIC, from_date, to_date, depth="quick")
        items = result.get("items", [])
        return _normalize(
            items,
            "Instagram",
            title_key="text",
            score_fn=lambda item: item.get("engagement", {}).get("views", 0),
        )
    except Exception as exc:
        print(f"  [Instagram] failed: {exc}")
        return []


def _collect_bluesky(from_date: str, to_date: str) -> list[dict[str, Any]]:
    try:
        from lib.bluesky import search_bluesky

        result = search_bluesky(AI_TOPIC, from_date, to_date, depth="quick")
        items = result.get("posts", [])
        return _normalize(
            items,
            "Bluesky",
            title_key="text",
            score_fn=lambda item: item.get("engagement", {}).get("likes", 0),
        )
    except Exception as exc:
        print(f"  [Bluesky] failed: {exc}")
        return []


def _collect_truthsocial(from_date: str, to_date: str) -> list[dict[str, Any]]:
    try:
        from lib.truthsocial import search_truthsocial

        result = search_truthsocial(AI_TOPIC, from_date, to_date, depth="quick")
        items = result.get("statuses", [])
        return _normalize(
            items,
            "TruthSocial",
            title_key="text",
            score_fn=lambda item: item.get("engagement", {}).get("likes", 0),
        )
    except Exception as exc:
        print(f"  [TruthSocial] failed: {exc}")
        return []


def _collect_polymarket(from_date: str, to_date: str) -> list[dict[str, Any]]:
    try:
        from lib.polymarket import search_polymarket

        result = search_polymarket(AI_TOPIC, from_date, to_date, depth="quick")
        events = result.get("events", [])
        articles: list[dict[str, Any]] = []
        for event in events:
            title = event.get("title", "")
            if not title:
                continue
            articles.append(
                {
                    "title": title,
                    "summary": event.get("description", title)[:400],
                    "source": "Polymarket",
                    "link": f"https://polymarket.com/event/{event.get('id', '')}",
                    "date": to_date,
                    "_score": 0,
                }
            )
        return articles
    except Exception as exc:
        print(f"  [Polymarket] failed: {exc}")
        return []


COLLECTORS: list[tuple[str, Callable[[str, str], list[dict[str, Any]]]]] = [
    ("Reddit", _collect_reddit),
    ("HN", _collect_hackernews),
    ("YouTube", _collect_youtube),
    ("TikTok", _collect_tiktok),
    ("Instagram", _collect_instagram),
    ("Bluesky", _collect_bluesky),
    ("TruthSocial", _collect_truthsocial),
    ("Polymarket", _collect_polymarket),
]


def collect_social(
    max_count: int = 50,
    *,
    now: datetime | None = None,
    cache_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Collect AI news from social / community sources with refresh budgeting."""
    now = now or datetime.now(timezone.utc)
    cache = _load_social_cache(cache_path)
    cache.setdefault("sources", {})

    print("[social] collecting AI news...")

    all_articles: list[dict[str, Any]] = []
    source_counts: dict[str, str] = {}
    pending = {}

    with ThreadPoolExecutor(max_workers=8) as pool:
        for name, collector in COLLECTORS:
            entry = cache["sources"].get(name)
            mode = _determine_refresh_mode(name, entry, now)
            if mode == "cache":
                cached_items = list(entry.get("items", []))
                source_counts[name] = f"{len(cached_items)} cache"
                all_articles.extend(cached_items)
                continue

            from_date, to_date = _build_date_window(mode, now)
            future = pool.submit(collector, from_date, to_date)
            pending[future] = (name, mode, from_date, entry)

        for future in as_completed(pending):
            name, mode, from_date, entry = pending[future]
            try:
                fresh_articles = future.result(timeout=60)
                fresh_articles = _filter_articles_to_window(fresh_articles, from_date)
                merged = _merge_cached_items(entry.get("items", []) if entry else [], fresh_articles, now=now)
                merged = merged[: SOURCE_CACHE_LIMITS.get(name, 25)]
                cache["sources"][name] = {
                    "last_refresh_at": now.isoformat(),
                    "last_mode": mode,
                    "items": merged,
                }
                source_counts[name] = f"{len(fresh_articles)} {mode}"
                all_articles.extend(merged)
            except Exception as exc:
                fallback = list(entry.get("items", [])) if entry else []
                if fallback:
                    all_articles.extend(fallback)
                    source_counts[name] = f"{len(fallback)} stale-cache"
                else:
                    source_counts[name] = "0"
                print(f"  [{name}] refresh failed: {exc}")

    _save_social_cache(cache, cache_path)

    for article in all_articles:
        article["engagement"] = article.get("_score", article.get("engagement", 0))

    from history import normalize_title

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    all_articles.sort(key=lambda article: _article_sort_score(article, now), reverse=True)
    for article in all_articles:
        key = normalize_title(article.get("title", ""))
        if key in seen:
            continue
        seen.add(key)
        article.pop("cached_at", None)
        article.pop("_score", None)
        unique.append(article)

    active = {name: count for name, count in source_counts.items() if count != "0"}
    summary = ", ".join(f"{name} {count}" for name, count in active.items())
    print(f"[social] total {len(unique[:max_count])} ({summary})")
    return unique[:max_count]


if __name__ == "__main__":  # pragma: no cover
    articles = collect_social()
    for index, article in enumerate(articles, start=1):
        print(f"\n[{index}] {article['title'][:80]}")
        print(f"    source: {article['source']}")
        print(f"    date:   {article.get('date', '')}")
        print(f"    link:   {article['link'][:80]}")
