"""Telegram preview/result notifications."""

from __future__ import annotations

import httpx

from config import TELEGRAM_BOT_TOKEN as BOT_TOKEN, TELEGRAM_CHAT_ID as CHAT_ID
from threads_poster import get_reply_sequence

TELEGRAM_API = "https://api.telegram.org"


def send_preview(content: dict) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("[telegram] BOT_TOKEN or CHAT_ID missing, skipping preview")
        return False
    return _send_message(_format_text_preview(content))


def send_result(result: dict) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        return False

    lines = ["[AI Threads post complete]"]
    if result.get("post_id"):
        lines.append(f"Main: {result['post_id']}")

    for key, value in result.items():
        if key in {"post_id", "link_id"}:
            continue
        if key.startswith("reply_") and value:
            lines.append(f"{key}: {value}")

    if result.get("link_id"):
        lines.append(f"Media/link: {result['link_id']}")

    return _send_message("\n".join(lines))


def _format_text_preview(content: dict) -> str:
    article = content.get("selected_article", {}) or {}
    sequence = get_reply_sequence(content, mode=content.get("mode", "informational"))

    lines = [
        "[AI Threads preview]",
        "",
        "Selected article",
        f"- title: {article.get('original_title', '?')}",
        f"- why: {article.get('reason', '')}",
        f"- source link: {content.get('source_link', '')}",
        "",
        "Main post",
        content.get("post_main", ""),
    ]

    if sequence:
        lines.append("")
        lines.append("Replies")
        for reply in sequence:
            lines.extend([f"- {reply['label']}: {reply['text']}"])

    media_plan = content.get("media_plan", {}) or {}
    if content.get("video_url"):
        lines.extend(["", f"Video: {content.get('video_url', '')}"])
    if content.get("og_image"):
        lines.extend(["", f"OG image: {content.get('og_image', '')}"])
    if any(media_plan.get(key) for key in ("preferred_type", "search_query", "reason")):
        lines.extend(
            [
                "",
                "Media plan",
                f"- type: {media_plan.get('preferred_type', 'none')}",
                f"- query: {media_plan.get('search_query', '')}",
                f"- reason: {media_plan.get('reason', '')}",
            ]
        )

    return "\n".join(lines)


def _send_message(text: str) -> bool:
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": CHAT_ID, "text": text},
            )
            if response.status_code == 200:
                print("[telegram] notification sent")
                return True
            print(f"[telegram] send failed: {response.status_code} {response.text[:200]}")
            return False
    except Exception as exc:
        print(f"[telegram] send error: {exc}")
        return False
