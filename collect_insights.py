"""과거 포스트의 Threads 인사이트 수집 스크립트.

GitHub Actions에서 main.py 실행 전에 호출.
포스팅 후 6시간 이상 지난 미수집 포스트의 성과를 가져온다.
"""

from config import THREADS_ACCESS_TOKEN
from performance_db import get_pending_insights, update_insights
from threads_insights import fetch_thread_insights


def main():
    if not THREADS_ACCESS_TOKEN:
        print("[인사이트] THREADS_ACCESS_TOKEN 미설정, 건너뜀")
        return

    pending = get_pending_insights()
    if not pending:
        print("[인사이트] 수집 대상 없음")
        return

    print(f"[인사이트] {len(pending)}개 포스트 성과 수집 중...")
    collected = 0
    for entry in pending:
        post_id = entry.get("post_id", "")
        if not post_id:
            continue
        insights = fetch_thread_insights(THREADS_ACCESS_TOKEN, post_id)
        if insights:
            update_insights(post_id, insights["likes"], insights["replies"], insights["views"])
            print(f"  {post_id}: L={insights['likes']} R={insights['replies']} V={insights['views']}")
            collected += 1

    print(f"[인사이트] {collected}/{len(pending)}개 수집 완료")


if __name__ == "__main__":
    main()
