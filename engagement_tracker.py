"""Engagement tracking & self-learning module.

Collects Threads Insights API data for past posts,
accumulates history, and analyzes patterns for prompt feedback.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from config import THREADS_ACCESS_TOKEN, THREADS_USER_ID, ENGAGEMENT_WEIGHTS, ENGAGEMENT_DAYS

OUTPUT_DIR = Path("output")
ENGAGEMENT_FILE = OUTPUT_DIR / "engagement.json"
INSIGHTS_METRICS = "views,likes,replies,reposts,quotes"


def fetch_insights(media_id, access_token=None):
    """Fetch engagement metrics for a single Threads post."""
    token = access_token or THREADS_ACCESS_TOKEN
    url = f"https://graph.threads.net/v1.0/{media_id}/insights"
    params = {"metric": INSIGHTS_METRICS, "access_token": token}

    with httpx.Client(timeout=15.0) as client:
        resp = client.get(url, params=params)
        if resp.status_code >= 400:
            print(f"    insights API 실패 ({media_id}): {resp.status_code} {resp.text[:200]}")
            return None

    data = resp.json().get("data", [])
    metrics = {}
    for item in data:
        name = item.get("name", "")
        values = item.get("values", [])
        if values:
            metrics[name] = values[0].get("value", 0)
    return metrics


def _compute_score(metrics):
    """Compute weighted engagement score."""
    return sum(metrics.get(k, 0) * w for k, w in ENGAGEMENT_WEIGHTS.items())


def collect_all_engagement(access_token=None):
    """Collect engagement for posts within ENGAGEMENT_DAYS that are at least 24h old."""
    token = access_token or THREADS_ACCESS_TOKEN
    if not token:
        print("  THREADS_ACCESS_TOKEN 미설정, engagement 수집 건너뜀")
        return []

    today = date.today()
    min_date = today - timedelta(days=ENGAGEMENT_DAYS)
    entries = []

    if not OUTPUT_DIR.exists():
        return entries

    for day_dir in sorted(OUTPUT_DIR.iterdir()):
        if not day_dir.is_dir():
            continue
        try:
            dir_date = date.fromisoformat(day_dir.name)
        except ValueError:
            continue

        # Only collect for posts between min_date and yesterday (24h+ old)
        if dir_date < min_date or dir_date >= today:
            continue

        post_file = day_dir / "post.json"
        if not post_file.exists():
            continue

        post_data = json.loads(post_file.read_text(encoding="utf-8"))
        posting_result = post_data.get("posting_result")
        if not posting_result:
            continue

        post_id = posting_result.get("post_id")
        if not post_id:
            continue

        # Skip if already collected
        if post_data.get("engagement"):
            continue

        print(f"    {day_dir.name} engagement 수집 중...")
        metrics = fetch_insights(post_id, token)
        if not metrics:
            continue

        score = _compute_score(metrics)
        engagement = {**metrics, "score": round(score, 1)}

        # Update post.json with engagement data
        post_data["engagement"] = engagement
        post_file.write_text(
            json.dumps(post_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        selected = post_data.get("selected_article", {})
        entries.append({
            "date": day_dir.name,
            "title": selected.get("original_title", ""),
            "post_main": post_data.get("post_main", "")[:100],
            "reply_casual": post_data.get("reply_casual", "")[:80],
            **engagement,
        })

    return entries


def load_engagement_history():
    """Load accumulated engagement history."""
    if not ENGAGEMENT_FILE.exists():
        return []
    return json.loads(ENGAGEMENT_FILE.read_text(encoding="utf-8"))


def save_engagement_history(new_entries):
    """Merge new entries into engagement.json (deduplicate by date)."""
    history = load_engagement_history()
    existing_dates = {e["date"] for e in history}

    for entry in new_entries:
        if entry["date"] in existing_dates:
            # Update existing entry
            history = [e if e["date"] != entry["date"] else entry for e in history]
        else:
            history.append(entry)

    history.sort(key=lambda e: e["date"], reverse=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ENGAGEMENT_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def analyze_patterns(history=None, top_n=3):
    """Analyze top/bottom performing posts and return patterns dict.

    Returns:
        {"top": [...], "bottom": [...], "avg": {...}} or None if insufficient data
    """
    if history is None:
        history = load_engagement_history()

    scored = [e for e in history if "score" in e]
    if len(scored) < 3:
        return None

    scored.sort(key=lambda e: e["score"], reverse=True)
    top = scored[:top_n]
    bottom = scored[-top_n:]

    # Compute averages
    avg = {}
    for metric in ENGAGEMENT_WEIGHTS:
        values = [e.get(metric, 0) for e in scored]
        avg[metric] = round(sum(values) / len(values), 1)
    avg["score"] = round(sum(e["score"] for e in scored) / len(scored), 1)

    return {"top": top, "bottom": bottom, "avg": avg}
