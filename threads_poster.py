"""Threads posting helpers.

Supports both:
- freeform `replies[]`
- legacy slot-based reply fields
"""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

GRAPH_API_BASE = "https://graph.threads.net/v1.0"
PUBLISH_RETRY_ATTEMPTS = 5
PUBLISH_RETRY_DELAY = 3
CONTAINER_WAIT_DELAY = 2
REPLY_DELAY = 5
THREADS_VISUAL_LINE_LIMIT = 34
THREADS_VISUAL_LINE_MIN = 14

REPLY_KEYS: dict[str, list[str]] = {
    "viral": [
        "reply_explain",
        "reply_important",
        "reply_action",
        "reply_counter",
        "reply_casual",
    ],
    "informational": [
        "reply_background",
        "reply_impact",
        "reply_compare",
        "reply_summary",
    ],
}

REPLY_LABELS: dict[str, str] = {
    "reply_explain": "Explain",
    "reply_important": "Why it matters",
    "reply_action": "What to do",
    "reply_counter": "Counterpoint",
    "reply_casual": "Closer",
    "reply_background": "Background",
    "reply_impact": "Impact",
    "reply_compare": "Compare",
    "reply_summary": "Summary",
}


def get_reply_sequence(content: dict[str, Any], mode: str) -> list[dict[str, str]]:
    """Return ordered reply entries for posting.

    Freeform replies[] win over legacy slot fields. Legacy fields are retained as a
    compatibility fallback for already-generated content and older tests.
    """
    replies = content.get("replies")
    if isinstance(replies, list) and any(str(item).strip() for item in replies):
        sequence: list[dict[str, str]] = []
        for index, reply in enumerate(replies, start=1):
            text = str(reply).strip()
            if not text:
                continue
            sequence.append(
                {
                    "key": f"reply_{index}",
                    "label": f"Reply {index}",
                    "text": text,
                }
            )
        return sequence

    sequence = []
    for key in REPLY_KEYS.get(mode, REPLY_KEYS["informational"]):
        text = str(content.get(key, "")).strip()
        if not text:
            continue
        sequence.append({"key": key, "label": REPLY_LABELS.get(key, key), "text": text})
    return sequence


def format_threads_display_text(text: str) -> str:
    """Add visible breathing room for the narrow Threads timeline."""
    lines = [line.strip() for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    blocks = ["\n".join(_wrap_threads_visual_line(line)) for line in lines if line]
    return "\n\n".join(blocks)


def _wrap_threads_visual_line(
    line: str,
    *,
    limit: int = THREADS_VISUAL_LINE_LIMIT,
    min_chunk: int = THREADS_VISUAL_LINE_MIN,
) -> list[str]:
    """Split long Korean visual lines before Threads creates ugly orphan wraps."""
    text = str(line or "").strip()
    if len(text) <= limit:
        return [text] if text else []

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        split_at = _find_threads_line_split(remaining, limit=limit, min_chunk=min_chunk)
        chunk = remaining[:split_at].strip()
        if not chunk:
            break
        chunks.append(chunk)
        remaining = remaining[split_at:].strip()

    if remaining:
        chunks.append(remaining)
    return chunks


def _find_threads_line_split(text: str, *, limit: int, min_chunk: int) -> int:
    window = text[: limit + 1]
    whitespace_indexes = [match.start() for match in re.finditer(r"\s+", window)]
    candidates = [index for index in whitespace_indexes if index >= min_chunk]
    if candidates:
        return candidates[-1]
    return min(limit, len(text))


def _is_retryable(response: httpx.Response) -> bool:
    if response.status_code >= 500:
        return True
    if response.status_code == 400:
        try:
            error = response.json().get("error", {})
        except Exception:
            return False
        return error.get("code") == 24 and error.get("error_subcode") == 4279009
    return False


def _create_text(
    client: httpx.Client,
    user_id: str,
    token: str,
    text: str,
    reply_to_id: str = "",
    link_attachment: str = "",
) -> str:
    params = {"media_type": "TEXT", "text": text, "access_token": token}
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    if link_attachment:
        params["link_attachment"] = link_attachment
    response = client.post(f"{GRAPH_API_BASE}/{user_id}/threads", params=params)
    if response.status_code >= 400:
        raise RuntimeError(f"text container failed: {response.status_code} {response.text[:500]}")
    return response.json()["id"]


def _create_image(
    client: httpx.Client,
    user_id: str,
    token: str,
    image_url: str,
    text: str = "",
    reply_to_id: str = "",
    link_attachment: str = "",
) -> str:
    params = {"media_type": "IMAGE", "image_url": image_url, "access_token": token}
    if text:
        params["text"] = text
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    if link_attachment:
        params["link_attachment"] = link_attachment
    response = client.post(f"{GRAPH_API_BASE}/{user_id}/threads", params=params)
    if response.status_code >= 400:
        raise RuntimeError(f"image container failed: {response.status_code} {response.text[:500]}")
    return response.json()["id"]


def _create_video(
    client: httpx.Client,
    user_id: str,
    token: str,
    video_url: str,
    text: str = "",
    reply_to_id: str = "",
    link_attachment: str = "",
) -> str:
    params = {"media_type": "VIDEO", "video_url": video_url, "access_token": token}
    if text:
        params["text"] = text
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    if link_attachment:
        params["link_attachment"] = link_attachment
    response = client.post(f"{GRAPH_API_BASE}/{user_id}/threads", params=params)
    if response.status_code >= 400:
        raise RuntimeError(f"video container failed: {response.status_code} {response.text[:500]}")
    return response.json()["id"]


def _wait_for_container(client: httpx.Client, container_id: str, token: str, timeout: int = 300) -> bool:
    attempts = max(1, timeout // 5)
    for index in range(attempts):
        response = client.get(
            f"{GRAPH_API_BASE}/{container_id}",
            params={"fields": "status,error_message", "access_token": token},
        )
        if response.status_code >= 400:
            raise RuntimeError(f"container status check failed: {response.status_code}")
        data = response.json()
        status = data.get("status", "")
        if status == "FINISHED":
            return True
        if status == "ERROR":
            raise RuntimeError(f"video processing failed: {data.get('error_message', 'unknown error')}")
        print(f"    video processing... ({(index + 1) * 5}s, status={status})")
        time.sleep(5)
    raise RuntimeError(f"video processing timeout ({timeout}s)")


def _publish(client: httpx.Client, user_id: str, token: str, creation_id: str) -> str:
    response: httpx.Response | None = None
    for attempt in range(1, PUBLISH_RETRY_ATTEMPTS + 1):
        response = client.post(
            f"{GRAPH_API_BASE}/{user_id}/threads_publish",
            params={"creation_id": creation_id, "access_token": token},
        )
        if response.status_code < 400:
            return response.json()["id"]
        if attempt < PUBLISH_RETRY_ATTEMPTS and _is_retryable(response):
            print(f"    publish retry {attempt}/{PUBLISH_RETRY_ATTEMPTS}...")
            time.sleep(PUBLISH_RETRY_DELAY)
            continue
    assert response is not None
    raise RuntimeError(f"publish failed: {response.status_code} {response.text[:500]}")


def _post_reply(client: httpx.Client, user_id: str, token: str, text: str, reply_to_id: str, label: str) -> str | None:
    if not text:
        return None
    time.sleep(REPLY_DELAY)
    creation_id = _create_text(client, user_id, token, text, reply_to_id=reply_to_id)
    time.sleep(CONTAINER_WAIT_DELAY)
    reply_id = _publish(client, user_id, token, creation_id)
    print(f"  {label}: {reply_id}")
    return reply_id


def post_thread(
    access_token: str,
    user_id: str,
    content: dict[str, Any],
    image_url: str | None = None,
    source_link: str | None = None,
    video_url: str | None = None,
    mode: str = "informational",
    strict_video: bool = False,
) -> dict[str, Any]:
    """Post a main thread plus ordered replies and optional media/link."""
    result: dict[str, Any] = {}
    reply_sequence = get_reply_sequence(content, mode=mode)

    with httpx.Client(timeout=30.0) as client:
        main_text = format_threads_display_text(str(content.get("post_main", "")).strip())

        link = source_link or ""
        # Inline the source URL in the main text so it's clickable in the post.
        # link_attachment is kept as metadata, but Threads hides the auto link
        # card when an image/video is also attached. Inlining guarantees the
        # source surfaces. Threads de-duplicates: the same URL won't render
        # twice if it's already shown as a card.
        if link:
            main_text = f"{main_text}\n\n{link}"

        if video_url:
            try:
                main_creation_id = _create_video(
                    client, user_id, access_token, video_url,
                    text=main_text, link_attachment=link,
                )
                _wait_for_container(client, main_creation_id, access_token)
                print("  Main media: video")
            except Exception as exc:
                if strict_video:
                    print(f"  Main video failed in strict mode: {exc}")
                    raise RuntimeError(f"main video failed in strict mode: {exc}") from exc
                print(f"  Main video failed, falling back: {exc}")
                video_url = None
                try:
                    if image_url:
                        main_creation_id = _create_image(
                            client, user_id, access_token, image_url,
                            text=main_text, link_attachment=link,
                        )
                        print("  Main media: image (video fallback)")
                    else:
                        main_creation_id = _create_text(
                            client, user_id, access_token, main_text,
                            link_attachment=link,
                        )
                        print("  Main media: text (video fallback)")
                except Exception as image_exc:
                    print(f"  Image fallback also failed: {image_exc}")
                    image_url = None
                    main_creation_id = _create_text(
                        client, user_id, access_token, main_text,
                        link_attachment=link,
                    )
                    print("  Main media: text (video+image fallback)")
        elif image_url:
            try:
                main_creation_id = _create_image(
                    client, user_id, access_token, image_url,
                    text=main_text, link_attachment=link,
                )
                print("  Main media: image")
            except Exception as exc:
                print(f"  Main image failed, falling back to text: {exc}")
                image_url = None
                main_creation_id = _create_text(
                    client, user_id, access_token, main_text,
                    link_attachment=link,
                )
        else:
            main_creation_id = _create_text(
                client, user_id, access_token, main_text,
                link_attachment=link,
            )

        time.sleep(CONTAINER_WAIT_DELAY)
        post_id = _publish(client, user_id, access_token, main_creation_id)
        print(f"  Main post: {post_id}")
        result["post_id"] = post_id

        # Cascade replies (R1 -> R2 -> R3) so Threads recognizes the chain as
        # a single author thread rather than independent siblings of the main post.
        parent_id = post_id
        for reply in reply_sequence:
            reply_id = _post_reply(
                client,
                user_id,
                access_token,
                format_threads_display_text(reply["text"]),
                parent_id,
                reply["label"],
            )
            if reply_id:
                result[reply["key"]] = reply_id
                parent_id = reply_id

    return result
