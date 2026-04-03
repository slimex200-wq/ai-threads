"""AI Threads — 8개 소스에서 트렌딩 AI 뉴스 1개를 골라 Threads 포스트.

포스팅 구조:
  메인: 핵심 뉴스 + So What
    └─ 대댓글: 모드별 reply 구조
    └─ 마지막: 원문 미디어 + 링크

Generator/Evaluator 패턴 적용:
  ai_writer(Generator) → qa_evaluator(Evaluator) → 통과 시 포스팅
  Ref: Anthropic "Harness Design for Long-Running Apps" (2026-03-24)

Usage:
    python main.py                        # 수집 → 생성 → QA → 포스팅 (기본: informational)
    python main.py --mode viral           # 바이럴 모드
    python main.py --dry-run              # 포스팅 없이 생성+QA만
    python main.py --collect-engagement   # engagement 수집만
"""

import argparse
import json
import re
import signal
import sys
from datetime import date, datetime
from pathlib import Path

import httpx

from config import (
    ANTHROPIC_API_KEY, THREADS_ACCESS_TOKEN, THREADS_USER_ID,
    MAX_DAILY_POSTS, FORCE_POST_HOUR, CONTENT_MODE, PIPELINE_TIMEOUT,
)


def count_posts_today():
    """Count how many posts were actually published today."""
    today_dir = Path("output") / date.today().isoformat()
    if not today_dir.exists():
        return 0
    count = 0
    for f in today_dir.glob("post*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("posting_result"):
                count += 1
        except Exception:
            pass
    return count


def fetch_og_video(url):
    """Extract og:video or detect YouTube URL from article page."""
    if not url:
        return None
    # Direct YouTube URL
    if "youtube.com/watch" in url or "youtu.be/" in url:
        return _get_youtube_direct_url(url)
    try:
        resp = httpx.get(url, timeout=10.0, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        # og:video meta tag
        match = re.search(
            r'<meta[^>]+property=["\']og:video["\'][^>]+content=["\']([^"\']+)["\']',
            resp.text, re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:video["\']',
                resp.text, re.IGNORECASE,
            )
        if match:
            video_url = match.group(1)
            if video_url.endswith(".mp4"):
                return video_url
            if "youtube.com" in video_url or "youtu.be" in video_url:
                return _get_youtube_direct_url(video_url)
        # Embedded YouTube iframe
        yt_match = re.search(
            r'(?:youtube\.com/embed/|youtu\.be/)([\w-]+)', resp.text
        )
        if yt_match:
            return _get_youtube_direct_url(f"https://www.youtube.com/watch?v={yt_match.group(1)}")
        return None
    except Exception as e:
        print(f"  og:video 추출 실패: {e}")
        return None


def _get_youtube_direct_url(youtube_url):
    """Use yt-dlp to get direct video URL (mp4, <=60s for Threads)."""
    import subprocess
    try:
        result = subprocess.run(
            ["yt-dlp", "--get-url", "-f", "mp4[duration<=60]/best[ext=mp4][duration<=60]/mp4/best[ext=mp4]", youtube_url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            url = result.stdout.strip().split("\n")[0]
            return url
        return None
    except Exception as e:
        print(f"  yt-dlp 실패: {e}")
        return None


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
    parser = argparse.ArgumentParser(description="AI Threads 포스트")
    parser.add_argument("--dry-run", action="store_true", help="포스팅 없이 생성만")
    parser.add_argument("--collect-engagement", action="store_true", help="engagement 수집만")
    parser.add_argument("--mode", choices=["viral", "informational"], default=None,
                        help="콘텐츠 모드 (기본: config.py CONTENT_MODE)")
    args = parser.parse_args()

    # 모드 결정: CLI > config > default
    mode = args.mode or CONTENT_MODE
    print(f"[모드] {mode}")

    # --collect-engagement: engagement만 수집하고 종료
    if args.collect_engagement:
        from engagement_tracker import collect_all_engagement, save_engagement_history
        entries = collect_all_engagement()
        if entries:
            save_engagement_history(entries)
            print(f"[완료] {len(entries)}개 포스트 engagement 수집 완료")
        else:
            print("[정보] 수집할 engagement 데이터가 없습니다")
        return

    if not ANTHROPIC_API_KEY:
        print("[에러] ANTHROPIC_API_KEY 미설정")
        sys.exit(1)
    if not args.dry_run and (not THREADS_ACCESS_TOKEN or not THREADS_USER_ID):
        print("[에러] THREADS_ACCESS_TOKEN 또는 THREADS_USER_ID 미설정")
        sys.exit(1)

    # 파이프라인 타임아웃 (Unix only — GitHub Actions는 Linux)
    if hasattr(signal, "SIGALRM"):
        def _timeout_handler(signum, frame):
            print(f"\n[타임아웃] 파이프라인 {PIPELINE_TIMEOUT}초 초과, 강제 종료")
            try:
                from telegram_notify import send_preview
                send_preview({"post_main": f"[타임아웃] 파이프라인 {PIPELINE_TIMEOUT}초 초과"})
            except Exception:
                pass
            sys.exit(1)
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(PIPELINE_TIMEOUT)

    # 스마트 스케줄러: 일일 포스팅 횟수 체크
    if not args.dry_run:
        posts_today = count_posts_today()
        if posts_today >= MAX_DAILY_POSTS:
            print(f"[스킵] 오늘 이미 {posts_today}회 포스팅 (최대 {MAX_DAILY_POSTS}회)")
            return

    # 0. 과거 포스트 engagement 수집 + 패턴 분석
    engagement_patterns = None
    try:
        from engagement_tracker import collect_all_engagement, save_engagement_history, analyze_patterns, load_engagement_history
        print("[0/7] 과거 포스트 engagement 수집 중...")
        entries = collect_all_engagement()
        if entries:
            save_engagement_history(entries)
            print(f"  {len(entries)}개 포스트 업데이트")
        history = load_engagement_history()
        if history:
            engagement_patterns = analyze_patterns(history, mode=mode)
            print(f"  패턴 분석 완료 (데이터 {len(history)}개)")
    except Exception as e:
        print(f"  engagement 수집 건너뜀: {e}")

    # 1. 멀티소스 수집
    print("\n[1/7] 8개 소스에서 AI 뉴스 수집 중...")
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
    print(f"\n[2/7] AI 관련 기사 필터링 중...")
    from news_filter import filter_by_keywords
    filtered = filter_by_keywords(articles, max_count=15) or articles[:15]
    print(f"  {len(filtered)}개 기사 통과")

    # 2.5. 히스토리 기반 중복 제거 (AI 호출 전 프리필터)
    from history import load_used_titles, save_title, filter_duplicates
    before_dedup = len(filtered)
    filtered = filter_duplicates(filtered)
    if before_dedup != len(filtered):
        print(f"  히스토리 중복 제거: {before_dedup} → {len(filtered)}개")

    if not filtered:
        print("[에러] 중복 제거 후 기사가 없습니다.")
        sys.exit(1)

    # engagement 높은 순 정렬 (AI가 상위 기사에 집중)
    filtered.sort(key=lambda a: a.get("engagement", 0), reverse=True)

    # 2.7. 스마트 스케줄러: 포스팅 가치 판단
    if not args.dry_run:
        from ai_writer import evaluate_worthiness
        posts_today = count_posts_today()
        is_last_run = datetime.now().hour >= FORCE_POST_HOUR
        force = is_last_run and posts_today == 0

        if not force:
            print(f"\n[2.7/7] 포스팅 가치 판단 중...")
            worthy, reason = evaluate_worthiness(filtered, mode=mode)
            if not worthy:
                print(f"  [스킵] {reason}")
                return
            print(f"  포스팅 진행: {reason}")

    # 3. 포스트 생성 + QA 평가 (Generator/Evaluator 루프)
    print(f"\n[3/7] 포스트 생성 중 ({mode})...")
    from ai_writer import generate_post
    from qa_evaluator import evaluate

    MAX_QA_RETRIES = 2
    used = load_used_titles()
    content = None
    qa_feedback = None  # 첫 시도는 피드백 없이

    for attempt in range(1, MAX_QA_RETRIES + 1):
        content = generate_post(
            filtered,
            used_titles=used,
            engagement_patterns=engagement_patterns,
            qa_feedback=qa_feedback,
            mode=mode,
        )

        article = content.get("selected_article", {})
        print(f"  선택: {article.get('original_title', '?')}")

        # QA 평가 (별도 Claude 호출)
        print(f"\n[4/7] QA 평가 중 (시도 {attempt}/{MAX_QA_RETRIES})...")
        qa_result = evaluate(content, mode=mode)
        print(f"  점수: {qa_result.score:.2f} | {'PASS' if qa_result.passed else 'FAIL'}")

        if qa_result.issues:
            for issue in qa_result.issues:
                print(f"  - {issue}")

        if qa_result.passed:
            if qa_result.suggestions:
                print(f"  제안: {', '.join(qa_result.suggestions[:2])}")
            break

        if attempt < MAX_QA_RETRIES:
            qa_feedback = {
                "previous_post": content,
                "issues": qa_result.issues,
                "suggestions": qa_result.suggestions,
                "score": qa_result.score,
            }
            print(f"  피드백 반영하여 재생성 중...")
        else:
            print(f"  [스킵] QA {MAX_QA_RETRIES}회 실패, 포스팅 건너뜀")
            return

    # 5. og:image/video 추출
    from urllib.parse import quote, urlparse, urlunparse
    raw_link = article.get("link", "")
    parsed = urlparse(raw_link)
    source_link = urlunparse(parsed._replace(path=quote(parsed.path)))
    print(f"\n[5/7] 원문 미디어 추출 중...")
    video_url = fetch_og_video(source_link)
    if video_url:
        print(f"  영상 발견: {video_url[:80]}...")
    og_image = fetch_og_image(source_link)
    if og_image:
        print(f"  og:image 확인: {og_image[:80]}...")
    if not video_url and not og_image:
        print(f"  미디어 없음")

    # 저장
    out_dir = Path("output") / date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    post_json_path = out_dir / "post.json"
    save_data = {
        **content,
        "mode": mode,
        "og_image": og_image,
        "video_url": video_url,
        "source_link": source_link,
        "qa_score": qa_result.score,
    }
    post_json_path.write_text(
        json.dumps(save_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    from telegram_notify import send_preview
    send_preview(content)

    if args.dry_run:
        print("\n[dry-run] 포스팅 건너뜀")
        return

    # 6. Threads 포스팅
    print(f"\n[6/7] Threads 포스팅 중...")
    from threads_poster import post_thread

    result = post_thread(
        access_token=THREADS_ACCESS_TOKEN,
        user_id=THREADS_USER_ID,
        content=content,
        image_url=og_image,
        source_link=source_link,
        video_url=video_url,
        mode=mode,
    )
    print(f"  포스팅 완료!")

    # [7/7] post.json에 posting_result 저장
    save_data["posting_result"] = result
    save_data["posted_at"] = datetime.now().isoformat()
    post_json_path.write_text(
        json.dumps(save_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if article.get("original_title"):
        save_title(article["original_title"], url=article.get("link", ""))

    from telegram_notify import send_result
    send_result(result)


if __name__ == "__main__":
    main()
