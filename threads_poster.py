"""Threads posting helpers.

Supports both:
- freeform `replies[]`
- legacy slot-based reply fields
"""

from __future__ import annotations

import time
from typing import Any

import httpx

GRAPH_API_BASE = "https://graph.threads.net/v1.0"
PUBLISH_RETRY_ATTEMPTS = 5
PUBLISH_RETRY_DELAY = 3
CONTAINER_WAIT_DELAY = 2
REPLY_DELAY = 5

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
) -> dict[str, Any]:
    """Post a main thread plus ordered replies and optional media/link."""
    result: dict[str, Any] = {}
    reply_sequence = get_reply_sequence(content, mode=mode)

    with httpx.Client(timeout=30.0) as client:
        main_text = str(content.get("post_main", "")).strip()

        link = source_link or ""

        if video_url:
            try:
                main_creation_id = _create_video(
                    client, user_id, access_token, video_url,
                    text=main_text, link_attachment=link,
                )
                _wait_for_container(client, main_creation_id, access_token)
                print("  Main media: video")
            except Exception as exc:
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

        for reply in reply_sequence:
            reply_id = _post_reply(
                client,
                user_id,
                access_token,
                reply["text"],
                post_id,
                reply["label"],
            )
            if reply_id:
                result[reply["key"]] = reply_id

    return result
