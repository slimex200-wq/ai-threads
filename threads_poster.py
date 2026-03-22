"""Threads API 자동 포스팅 모듈.

카드뉴스 이미지를 캐러셀로 포스트하고, 댓글로 원문 링크를 달기.
Threads API 2단계 플로우: 컨테이너 생성 → 발행.
"""

import argparse
import os
import sys
import time
from datetime import date
from pathlib import Path

import httpx

GRAPH_API_BASE = "https://graph.threads.net/v1.0"
PUBLISH_RETRY_ATTEMPTS = 5
PUBLISH_RETRY_DELAY = 3  # seconds
CONTAINER_WAIT_DELAY = 2  # seconds between container creation and publish
MAX_CAROUSEL_ITEMS = 20


def _raise_for_error(response: httpx.Response, operation: str) -> None:
    """API 에러 시 상세 메시지 포함 예외 발생."""
    if response.status_code >= 400:
        body = (response.text or "").strip()
        raise RuntimeError(
            f"{operation} failed: status={response.status_code} body={body[:500]}"
        )


def _should_retry_publish(response: httpx.Response) -> bool:
    """Media Not Found 에러만 재시도 가능."""
    if response.status_code != 400:
        return False
    try:
        error = response.json().get("error", {})
    except Exception:
        return False
    return (
        error.get("code") == 24
        and error.get("error_subcode") == 4279009
    )


def create_image_container(
    client: httpx.Client, user_id: str, access_token: str, image_url: str
) -> str:
    """단일 이미지 컨테이너 생성 → creation_id 반환."""
    response = client.post(
        f"{GRAPH_API_BASE}/{user_id}/threads",
        params={
            "media_type": "IMAGE",
            "image_url": image_url,
            "access_token": access_token,
        },
    )
    _raise_for_error(response, f"create image container ({image_url})")
    return response.json()["id"]


def create_carousel_container(
    client: httpx.Client,
    user_id: str,
    access_token: str,
    children_ids: list[str],
    caption: str,
) -> str:
    """캐러셀 컨테이너 생성 → creation_id 반환."""
    response = client.post(
        f"{GRAPH_API_BASE}/{user_id}/threads",
        params={
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "text": caption,
            "access_token": access_token,
        },
    )
    _raise_for_error(response, "create carousel container")
    return response.json()["id"]


def create_text_container(
    client: httpx.Client,
    user_id: str,
    access_token: str,
    text: str,
    reply_to_id: str = "",
) -> str:
    """텍스트 컨테이너 생성 → creation_id 반환. reply_to_id가 있으면 댓글."""
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": access_token,
    }
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    response = client.post(
        f"{GRAPH_API_BASE}/{user_id}/threads",
        params=params,
    )
    _raise_for_error(response, "create text container")
    return response.json()["id"]


def create_carousel_reply_container(
    client: httpx.Client,
    user_id: str,
    access_token: str,
    children_ids: list[str],
    reply_to_id: str,
) -> str:
    """캐러셀 댓글 컨테이너 생성 → creation_id 반환."""
    response = client.post(
        f"{GRAPH_API_BASE}/{user_id}/threads",
        params={
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "reply_to_id": reply_to_id,
            "access_token": access_token,
        },
    )
    _raise_for_error(response, "create carousel reply container")
    return response.json()["id"]


def publish_container(
    client: httpx.Client, user_id: str, access_token: str, creation_id: str
) -> str:
    """컨테이너 발행 → post_id 반환. Media Not Found 시 재시도."""
    for attempt in range(1, PUBLISH_RETRY_ATTEMPTS + 1):
        response = client.post(
            f"{GRAPH_API_BASE}/{user_id}/threads_publish",
            params={
                "creation_id": creation_id,
                "access_token": access_token,
            },
        )
        if response.status_code < 400:
            return response.json()["id"]

        if attempt < PUBLISH_RETRY_ATTEMPTS and _should_retry_publish(response):
            print(f"  → Media Not Found, 재시도 {attempt}/{PUBLISH_RETRY_ATTEMPTS}...")
            time.sleep(PUBLISH_RETRY_DELAY)
            continue

        _raise_for_error(response, "publish container")

    _raise_for_error(response, "publish container (retries exhausted)")
    return ""  # unreachable


def check_url_accessible(url: str, timeout: int = 10) -> bool:
    """URL이 접근 가능한지 HEAD 요청으로 확인."""
    try:
        resp = httpx.head(url, timeout=timeout, follow_redirects=True)
        return resp.status_code == 200
    except Exception:
        return False


def wait_for_pages_deployment(base_url: str, image_path: str, max_wait: int = 120) -> bool:
    """GitHub Pages 배포 완료까지 대기. 이미지 URL 접근 가능 여부로 판단."""
    url = f"{base_url}/{image_path}"
    print(f"  → Pages 배포 대기 중... ({url})")
    waited = 0
    interval = 10
    while waited < max_wait:
        if check_url_accessible(url):
            print(f"  → Pages 배포 확인 완료 ({waited}초)")
            return True
        time.sleep(interval)
        waited += interval
        print(f"  → 대기 중... ({waited}/{max_wait}초)")
    print(f"  → Pages 배포 대기 시간 초과 ({max_wait}초)")
    return False


def post_carousel_with_reply(
    access_token: str,
    user_id: str,
    image_urls: list[str],
    caption: str,
    reply_text: str | None = None,
) -> dict:
    """캐러셀 포스트 (caption + 이미지) + 링크 댓글.

    구조:
        1) 캐러셀 포스트 (caption 텍스트 + 이미지들 — 하나의 글)
        2) 텍스트 댓글 (links)

    Returns:
        {"post_id": str, "reply_id": str | None}
    """
    if len(image_urls) > MAX_CAROUSEL_ITEMS:
        image_urls = image_urls[:MAX_CAROUSEL_ITEMS]

    with httpx.Client(timeout=30.0) as client:
        # 1. 각 이미지별 컨테이너 생성
        print(f"[Threads] 이미지 컨테이너 생성 중... ({len(image_urls)}장)")
        children_ids = []
        for i, url in enumerate(image_urls, 1):
            container_id = create_image_container(client, user_id, access_token, url)
            children_ids.append(container_id)
            print(f"  → 이미지 {i}/{len(image_urls)}: {container_id}")

        # 2. 캐러셀 컨테이너 생성 (caption 포함)
        print("[Threads] 캐러셀 포스트 생성 중...")
        time.sleep(CONTAINER_WAIT_DELAY)
        carousel_id = create_carousel_container(
            client, user_id, access_token, children_ids, caption
        )
        print(f"  → 캐러셀: {carousel_id}")

        # 3. 캐러셀 발행
        time.sleep(CONTAINER_WAIT_DELAY)
        post_id = publish_container(client, user_id, access_token, carousel_id)
        print(f"  → 발행 완료: {post_id}")

        # 4. 링크 댓글
        reply_id = None
        if reply_text:
            print("[Threads] 링크 댓글 작성 중...")
            time.sleep(CONTAINER_WAIT_DELAY)
            reply_container_id = create_text_container(
                client, user_id, access_token, reply_text, reply_to_id=post_id
            )
            time.sleep(CONTAINER_WAIT_DELAY)
            reply_id = publish_container(client, user_id, access_token, reply_container_id)
            print(f"  → 링크 댓글 발행 완료: {reply_id}")

    return {"post_id": post_id, "reply_id": reply_id}


def main():
    parser = argparse.ArgumentParser(description="Threads 자동 포스팅")
    parser.add_argument(
        "--date", type=str, default=date.today().isoformat(),
        help="카드뉴스 날짜 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--base-url", type=str,
        default="https://slimex200-wq.github.io/ai-cardnews",
        help="GitHub Pages base URL",
    )
    parser.add_argument(
        "--output", type=str, default="output",
        help="로컬 output 디렉토리",
    )
    parser.add_argument(
        "--skip-wait", action="store_true",
        help="Pages 배포 대기 건너뛰기",
    )
    args = parser.parse_args()

    access_token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    user_id = os.environ.get("THREADS_USER_ID", "")

    if not access_token or not user_id:
        print("[Threads] THREADS_ACCESS_TOKEN 또는 THREADS_USER_ID 미설정, 건너뜀")
        sys.exit(0)

    # 오늘 날짜 output 확인
    output_dir = Path(args.output) / args.date
    if not output_dir.exists():
        print(f"[Threads] 출력 폴더 없음: {output_dir}")
        sys.exit(1)

    # 카드 이미지 목록
    card_files = sorted(output_dir.glob("card-*.png"))
    if not card_files:
        print("[Threads] 카드 이미지 없음")
        sys.exit(1)

    # caption / links 읽기
    caption_file = output_dir / "caption.txt"
    links_file = output_dir / "links.txt"

    caption = caption_file.read_text(encoding="utf-8").strip() if caption_file.exists() else ""
    links_text = links_file.read_text(encoding="utf-8").strip() if links_file.exists() else None

    if not caption:
        print("[Threads] caption.txt 비어있음")
        sys.exit(1)

    # 이미지 URL 생성
    image_urls = [
        f"{args.base_url}/cards/{args.date}/{f.name}" for f in card_files
    ]

    # Pages 배포 대기
    if not args.skip_wait:
        first_image_path = f"cards/{args.date}/{card_files[0].name}"
        if not wait_for_pages_deployment(args.base_url, first_image_path):
            print("[Threads] Pages 배포 미완료, 포스팅 건너뜀")
            sys.exit(1)

    # 포스팅
    print(f"\n[Threads] 캐러셀 포스트 시작 ({len(image_urls)}장 + caption)")
    result = post_carousel_with_reply(
        access_token=access_token,
        user_id=user_id,
        image_urls=image_urls,
        caption=caption,
        reply_text=links_text,
    )

    print(f"\n[Threads] 완료!")
    print(f"  → 포스트 ID: {result['post_id']}")
    if result["reply_id"]:
        print(f"  → 링크 댓글 ID: {result['reply_id']}")


if __name__ == "__main__":
    main()
