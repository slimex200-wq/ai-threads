"""Engagement tracking and lightweight self-learning summaries."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

from config import ENGAGEMENT_DAYS, ENGAGEMENT_WEIGHTS, THREADS_ACCESS_TOKEN

OUTPUT_DIR = Path("output")
ENGAGEMENT_FILE = OUTPUT_DIR / "engagement.json"
INSIGHTS_METRICS = "views,likes,replies,reposts,quotes"


def fetch_insights(media_id: str, access_token: str | None = None) -> dict[str, int] | None:
    token = access_token or THREADS_ACCESS_TOKEN
    url = f"https://graph.threads.net/v1.0/{media_id}/insights"
    params = {"metric": INSIGHTS_METRICS, "access_token": token}

    with httpx.Client(timeout=15.0) as client:
        response = client.get(url, params=params)
        if response.status_code >= 400:
            print(f"    insights API failed ({media_id}): {response.status_code} {response.text[:200]}")
            return None

    data = response.json().get("data", [])
    metrics: dict[str, int] = {}
    for item in data:
        name = item.get("name", "")
        values = item.get("values", [])
        if values:
            metrics[name] = values[0].get("value", 0)
    return metrics


def _compute_score(metrics: dict[str, int]) -> float:
    return sum(metrics.get(key, 0) * weight for key, weight in ENGAGEMENT_WEIGHTS.items())


def _reply_preview(post_data: dict[str, Any]) -> str:
    replies = post_data.get("replies")
    if isinstance(replies, list):
        for reply in replies:
            text = str(reply).strip()
            if text:
                return text[:80]
    return str(post_data.get("reply_casual", "")).strip()[:80]


def collect_all_engagement(access_token: str | None = None) -> list[dict[str, Any]]:
    token = access_token or THREADS_ACCESS_TOKEN
    if not token:
        print("  THREADS_ACCESS_TOKEN missing, skipping engagement collection")
        return []

    today = date.today()
    min_date = today - timedelta(days=ENGAGEMENT_DAYS)
    entries: list[dict[str, Any]] = []

    if not OUTPUT_DIR.exists():
        return entries

    for day_dir in sorted(OUTPUT_DIR.iterdir()):
        if not day_dir.is_dir():
            continue

        try:
            dir_date = date.fromisoformat(day_dir.name)
        except ValueError:
            continue

        if dir_date < min_date or dir_date >= today:
            continue

        post_file = day_dir / "post.json"
        if not post_file.exists():
            continue

        post_data = json.loads(post_file.read_text(encoding="utf-8"))
        posting_result = post_data.get("posting_result") or {}
        post_id = posting_result.get("post_id")
        if not post_id or post_data.get("engagement"):
            continue

        print(f"    collecting engagement for {day_dir.name}...")
        metrics = fetch_insights(post_id, token)
        if not metrics:
            continue

        score = round(_compute_score(metrics), 1)
        engagement = {**metrics, "score": score}
        post_data["engagement"] = engagement
        post_file.write_text(json.dumps(post_data, ensure_ascii=False, indent=2), encoding="utf-8")

        selected = post_data.get("selected_article", {}) or {}
        entries.append(
            {
                "date": day_dir.name,
                "mode": post_data.get("mode", "viral"),
                "title": selected.get("original_title", ""),
                "post_main": str(post_data.get("post_main", ""))[:100],
                "reply_preview": _reply_preview(post_data),
                "reply_count": len(post_data.get("replies", [])) if isinstance(post_data.get("replies"), list) else 0,
                **engagement,
            }
        )

    return entries


def load_engagement_history() -> list[dict[str, Any]]:
    if not ENGAGEMENT_FILE.exists():
        return []
    return json.loads(ENGAGEMENT_FILE.read_text(encoding="utf-8"))


def save_engagement_history(new_entries: list[dict[str, Any]]) -> None:
    history = load_engagement_history()
    existing_dates = {entry["date"] for entry in history}

    for entry in new_entries:
        if entry["date"] in existing_dates:
            history = [current if current["date"] != entry["date"] else entry for current in history]
        else:
            history.append(entry)

    history.sort(key=lambda entry: entry["date"], reverse=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ENGAGEMENT_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def analyze_patterns(
    history: list[dict[str, Any]] | None = None,
    top_n: int = 3,
    mode: str | None = None,
) -> dict[str, Any] | None:
    if history is None:
        history = load_engagement_history()

    scored = [entry for entry in history if "score" in entry]
    if mode is not None:
        scored = [entry for entry in scored if entry.get("mode") == mode]

    if len(scored) < 3:
        return None

    scored.sort(key=lambda entry: entry["score"], reverse=True)
    top = scored[:top_n]
    bottom = scored[-top_n:]

    avg: dict[str, float] = {}
    for metric in ENGAGEMENT_WEIGHTS:
        values = [entry.get(metric, 0) for entry in scored]
        avg[metric] = round(sum(values) / len(values), 1)
    avg["score"] = round(sum(entry["score"] for entry in scored) / len(scored), 1)

    return {"top": top, "bottom": bottom, "avg": avg}
