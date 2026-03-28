"""AI Threads — 8개 소스에서 트렌딩 AI 뉴스 1개를 골라 Threads 바이럴 포스트.

포스팅 구조:
  메인: 바이럴 후킹 (의견 + 질문)
    └─ 대댓글 1: 분석 (의미/중요성/행동)
    └─ 대댓글 2: 가벼운 첫 댓글
    └─ 대댓글 3: 원문 이미지 + 링크

Usage:
    python main.py              # 수집 → 생성 → 포스팅
    python main.py --dry-run    # 포스팅 없이 생성만
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import httpx

from config import ANTHROPIC_API_KEY, THREADS_ACCESS_TOKEN, THREADS_USER_ID


def fetch_og_image(url):
    """URL에서 og:image 메타태그 추출."""
    if not url:
        return None
    try:
        resp = httpx.get(url, timeout=10.0, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            resp.text, re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                resp.text, re.IGNORECASE,
            )
        return match.group(1) if match else None
    except Exception as e:
        print(f"  og:image 추출 실패: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="AI Threads 바이럴 포스트")
    parser.add_argument("--dry-run", action="store_true", help="포스팅 없이 생성만")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("[에러] ANTHROPIC_API_KEY 미설정")
        sys.exit(1)
    if not args.dry_run and (not THREADS_ACCESS_TOKEN or not THREADS_USER_ID):
        print("[에러] THREADS_ACCESS_TOKEN 또는 THREADS_USER_ID 미설정")
        sys.exit(1)

    # 1. 멀티소스 수집
    print("[1/5] 8개 소스에서 AI 뉴스 수집 중...")
    from social_collector import collect_social
    from rss_collector import collect_news

    articles = []
    try:
        articles = collect_social(max_count=30)
    except Exception as e:
        print(f"  소셜 수집 실패: {e}")

    rss = collect_news(max_count=50)
    if rss:
        articles = articles + rss
        print(f"  RSS {len(rss)}개 보충, 총 {len(articles)}개")

    if not articles:
        print("[에러] 뉴스를 수집하지 못했습니다.")
        sys.exit(1)

    # 2. AI 키워드 필터링
    print(f"\n[2/5] AI 관련 기사 필터링 중...")
    from news_filter import filter_by_keywords
    filtered = filter_by_keywords(articles, max_count=15) or articles[:15]
    print(f"  {len(filtered)}개 기사 통과")

    # 3. 포스트 생성
    print(f"\n[3/5] 바이럴 포스트 생성 중...")
    from datetime import datetime
    from history import load_used_titles, save_title
    from ai_writer import generate_post
    from performance_db import get_top_posts, get_bottom_posts, get_recent_topics

    kst_hour = datetime.now().hour
    content = generate_post(
        filtered,
        used_titles=load_used_titles(),
        recent_topics=get_recent_topics(6),
        hour=kst_hour,
        top_posts=get_top_posts(3),
        bottom_posts=get_bottom_posts(2),
    )

    article = content.get("selected_article", {})
    print(f"  선택: {article.get('original_title', '?')}")

    # 4. og:image 추출
    source_link = article.get("link", "")
    print(f"\n[4/5] 원문 이미지 추출 중...")
    og_image = fetch_og_image(source_link)
    if og_image:
        print(f"  og:image 확인: {og_image[:80]}...")
    else:
        print(f"  og:image 없음")

    # 저장
    out_dir = Path("output") / date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    save_data = {**content, "og_image": og_image, "source_link": source_link}
    (out_dir / "post.json").write_text(
        json.dumps(save_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    from telegram_notify import send_preview
    send_preview(content)

    if args.dry_run:
        print("\n[dry-run] 포스팅 건너뜀")
        return

    # 5. Threads 포스팅
    print(f"\n[5/5] Threads 포스팅 중...")
    from threads_poster import post_thread

    result = post_thread(
        access_token=THREADS_ACCESS_TOKEN,
        user_id=THREADS_USER_ID,
        content=content,
        image_url=og_image,
        source_link=source_link,
    )
    print(f"  포스팅 완료!")

    if article.get("original_title"):
        save_title(article["original_title"])

    # 성과 추적용 DB 저장
    if result.get("post_id"):
        from performance_db import save_post
        save_post(result["post_id"], content, kst_hour)
        print(f"  성과 추적 등록: {result['post_id']}")

    from telegram_notify import send_result
    send_result(result)


if __name__ == "__main__":
    main()
