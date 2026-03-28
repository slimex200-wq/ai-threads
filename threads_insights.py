"""Threads Insights API — 포스트 성과 지표 수집."""

import httpx

GRAPH_API_BASE = "https://graph.threads.net/v1.0"


def fetch_thread_insights(access_token, thread_id):
    """개별 스레드의 좋아요/댓글/조회수 조회.

    Returns:
        {"likes": int, "replies": int, "views": int} or None on failure.
    """
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"{GRAPH_API_BASE}/{thread_id}",
                params={
                    "fields": "id,likes,replies,views",
                    "access_token": access_token,
                },
            )
            if resp.status_code >= 400:
                print(f"  [인사이트] {thread_id} 조회 실패: {resp.status_code}")
                return None
            data = resp.json()
            return {
                "likes": data.get("likes", 0),
                "replies": data.get("replies", 0),
                "views": data.get("views", 0),
            }
    except Exception as e:
        print(f"  [인사이트] {thread_id} 에러: {e}")
        return None
