"""Threads API 포스팅 모듈 — 메인 + 5개 대댓글 + 이미지/링크."""

import time
import httpx

GRAPH_API_BASE = "https://graph.threads.net/v1.0"
PUBLISH_RETRY_ATTEMPTS = 5
PUBLISH_RETRY_DELAY = 3
CONTAINER_WAIT_DELAY = 2
REPLY_DELAY = 5

REPLY_KEYS: dict[str, list[str]] = {
    "viral": [
        "reply_explain", "reply_important", "reply_action",
        "reply_counter", "reply_casual",
    ],
    "informational": [
        "reply_background", "reply_impact",
        "reply_compare", "reply_summary",
    ],
}

REPLY_LABELS: dict[str, str] = {
    "reply_explain": "쉽게 말하면",
    "reply_important": "왜 중요",
    "reply_action": "뭘 해야",
    "reply_counter": "반대 의견",
    "reply_casual": "가벼운 한마디",
    "reply_background": "배경",
    "reply_impact": "영향",
    "reply_compare": "비교",
    "reply_summary": "정리",
}


def _is_retryable(response):
    if response.status_code >= 500:
        return True
    if response.status_code == 400:
        try:
            error = response.json().get("error", {})
        except Exception:
            return False
        return error.get("code") == 24 and error.get("error_subcode") == 4279009
    return False


def _create_text(client, user_id, token, text, reply_to_id=""):
    params = {"media_type": "TEXT", "text": text, "access_token": token}
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    resp = client.post(f"{GRAPH_API_BASE}/{user_id}/threads", params=params)
    if resp.status_code >= 400:
        raise RuntimeError(f"text container failed: {resp.status_code} {resp.text[:500]}")
    return resp.json()["id"]


def _create_image(client, user_id, token, image_url, text="", reply_to_id=""):
    params = {"media_type": "IMAGE", "image_url": image_url, "access_token": token}
    if text:
        params["text"] = text
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    resp = client.post(f"{GRAPH_API_BASE}/{user_id}/threads", params=params)
    if resp.status_code >= 400:
        raise RuntimeError(f"image container failed: {resp.status_code} {resp.text[:500]}")
    return resp.json()["id"]


def _create_video(client, user_id, token, video_url, text="", reply_to_id=""):
    params = {"media_type": "VIDEO", "video_url": video_url, "access_token": token}
    if text:
        params["text"] = text
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    resp = client.post(f"{GRAPH_API_BASE}/{user_id}/threads", params=params)
    if resp.status_code >= 400:
        raise RuntimeError(f"video container failed: {resp.status_code} {resp.text[:500]}")
    return resp.json()["id"]


def _wait_for_container(client, container_id, token, timeout=300):
    """Poll container status until FINISHED (video processing)."""
    import math
    attempts = math.ceil(timeout / 5)
    for i in range(attempts):
        resp = client.get(
            f"{GRAPH_API_BASE}/{container_id}",
            params={"fields": "status,error_message", "access_token": token},
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"container status check failed: {resp.status_code}")
        data = resp.json()
        status = data.get("status", "")
        if status == "FINISHED":
            return True
        if status == "ERROR":
            raise RuntimeError(f"video processing failed: {data.get('error_message', 'unknown')}")
        print(f"    비디오 처리 중... ({(i+1)*5}s, status={status})")
        time.sleep(5)
    raise RuntimeError(f"video processing timeout ({timeout}s)")


def _publish(client, user_id, token, creation_id):
    for attempt in range(1, PUBLISH_RETRY_ATTEMPTS + 1):
        resp = client.post(
            f"{GRAPH_API_BASE}/{user_id}/threads_publish",
            params={"creation_id": creation_id, "access_token": token},
        )
        if resp.status_code < 400:
            return resp.json()["id"]
        if attempt < PUBLISH_RETRY_ATTEMPTS and _is_retryable(resp):
            print(f"    발행 재시도 {attempt}/{PUBLISH_RETRY_ATTEMPTS}...")
            time.sleep(PUBLISH_RETRY_DELAY)
            continue
    raise RuntimeError(f"publish failed: {resp.status_code} {resp.text[:500]}")


def _post_reply(client, user_id, token, text, reply_to_id, label):
    """텍스트 대댓글 하나 발행."""
    if not text:
        return None
    time.sleep(REPLY_DELAY)
    cid = _create_text(client, user_id, token, text, reply_to_id=reply_to_id)
    time.sleep(CONTAINER_WAIT_DELAY)
    rid = _publish(client, user_id, token, cid)
    print(f"  {label}: {rid}")
    return rid


def post_thread(
    access_token: str,
    user_id: str,
    content: dict,
    image_url: str | None = None,
    source_link: str | None = None,
    video_url: str | None = None,
    mode: str = "informational",
) -> dict:
    """Threads 스레드 포스팅.

    구조:
      메인 → 모드별 대댓글 순서대로 → 미디어+링크

    Args:
        content: ai_writer.generate_post() 결과
        image_url: og:image URL (없으면 건너뜀)
        source_link: 원문 URL (없으면 건너뜀)
        video_url: 직접 비디오 URL (있으면 이미지 대신 비디오 포스팅)
        mode: 대댓글 구성 모드 — "viral" 또는 "informational" (기본값)

    Returns:
        dict with post_id and reply IDs
    """
    result = {}

    with httpx.Client(timeout=30.0) as client:
        # 메인 포스트
        main_text = content["post_main"]
        main_cid = _create_text(client, user_id, access_token, main_text)
        time.sleep(CONTAINER_WAIT_DELAY)
        post_id = _publish(client, user_id, access_token, main_cid)
        print(f"  메인 포스트: {post_id}")
        result["post_id"] = post_id

        # 대댓글 순서대로 (모드별)
        for key in REPLY_KEYS.get(mode, REPLY_KEYS["informational"]):
            label = REPLY_LABELS.get(key, key)
            rid = _post_reply(
                client, user_id, access_token,
                content.get(key, ""), post_id, label,
            )
            if rid:
                result[key] = rid

        # 미디어 + 링크 대댓글 (비디오 > 이미지 > 텍스트)
        if video_url or image_url or source_link:
            time.sleep(REPLY_DELAY)
            link_text = source_link if source_link else ""
            try:
                if video_url:
                    cid = _create_video(
                        client, user_id, access_token, video_url,
                        text=link_text, reply_to_id=post_id,
                    )
                    _wait_for_container(client, cid, access_token)
                elif image_url:
                    cid = _create_image(
                        client, user_id, access_token, image_url,
                        text=link_text, reply_to_id=post_id,
                    )
                else:
                    cid = _create_text(
                        client, user_id, access_token, link_text, reply_to_id=post_id,
                    )
                time.sleep(CONTAINER_WAIT_DELAY)
                result["link_id"] = _publish(client, user_id, access_token, cid)
                print(f"  미디어: {result['link_id']}")
            except Exception as e:
                print(f"  미디어 실패 (건너뜀): {e}")
                # Fallback to image if video fails
                if video_url and image_url:
                    try:
                        print(f"  이미지로 폴백 시도...")
                        cid = _create_image(
                            client, user_id, access_token, image_url,
                            text=link_text, reply_to_id=post_id,
                        )
                        time.sleep(CONTAINER_WAIT_DELAY)
                        result["link_id"] = _publish(client, user_id, access_token, cid)
                        print(f"  이미지 폴백 성공: {result['link_id']}")
                    except Exception as e2:
                        print(f"  이미지 폴백도 실패: {e2}")

    return result
