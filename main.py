"""AI Threads pipeline.

Flow:
1. collect engagement history
2. collect candidate articles
3. filter / deduplicate / score
4. generate freeform thread
5. QA and optional rewrite
6. attach related media
7. post to Threads or dry-run
8. save structured learning logs for future training
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

import httpx

from config import (
    ANTHROPIC_API_KEY,
    CONTENT_MODE,
    FORCE_POST_HOUR,
    MAX_DAILY_POSTS,
    PIPELINE_TIMEOUT,
    THREADS_ACCESS_TOKEN,
    THREADS_USER_ID,
)
from candidate_ranking import score_candidate
from media_helpers import build_content_with_media, normalize_source_link


def count_posts_today() -> int:
    today_dir = Path("output") / date.today().isoformat()
    if not today_dir.exists():
        return 0

    count = 0
    for path in today_dir.glob("post*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("posting_result"):
                count += 1
        except Exception:
            continue
    return count


def fetch_og_video(url: str | None) -> str | None:
    if not url:
        return None

    if "youtube.com/watch" in url or "youtu.be/" in url:
        return _get_youtube_direct_url(url)

    try:
        response = httpx.get(
            url,
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if response.status_code != 200:
            return None

        match = re.search(
            r'<meta[^>]+property=["\']og:video["\'][^>]+content=["\']([^"\']+)["\']',
            response.text,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:video["\']',
                response.text,
                re.IGNORECASE,
            )
        if match:
            video_url = match.group(1)
            if video_url.endswith(".mp4"):
                return video_url
            if "youtube.com" in video_url or "youtu.be" in video_url:
                return _get_youtube_direct_url(video_url)

        youtube_match = re.search(r'(?:youtube\.com/embed/|youtu\.be/)([\w-]+)', response.text)
        if youtube_match:
            return _get_youtube_direct_url(f"https://www.youtube.com/watch?v={youtube_match.group(1)}")
        return None
    except Exception as exc:
        print(f"  og:video extraction failed: {exc}")
        return None


def _get_youtube_direct_url(youtube_url: str) -> str | None:
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--get-url",
                "-f",
                "mp4[duration<=60]/best[ext=mp4][duration<=60]/mp4/best[ext=mp4]",
                youtube_url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0]
        return None
    except Exception as exc:
        print(f"  yt-dlp direct-url lookup failed: {exc}")
        return None


def _download_and_upload_video(youtube_url: str) -> str | None:
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not supabase_service_key:
        print("  Supabase not configured, falling back to direct URL")
        return _get_youtube_direct_url(youtube_url)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "promo.mp4")
            result = subprocess.run(
                [
                    "yt-dlp",
                    "-f",
                    "mp4[height<=720]/best[ext=mp4][height<=720]",
                    "-o",
                    out_path,
                    "--no-warnings",
                    youtube_url,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0 or not os.path.exists(out_path):
                print(f"  download failed: {result.stderr[:200]}")
                return None

            file_size = os.path.getsize(out_path)
            if file_size > 50 * 1024 * 1024:
                print(f"  video too large: {file_size // (1024 * 1024)}MB")
                return None

            filename = f"promo-{date.today().isoformat()}.mp4"
            upload_url = f"{supabase_url}/storage/v1/object/videos/{filename}"

            with open(out_path, "rb") as handle:
                response = httpx.put(
                    upload_url,
                    content=handle.read(),
                    headers={
                        "Authorization": f"Bearer {supabase_service_key}",
                        "Content-Type": "video/mp4",
                        "x-upsert": "true",
                    },
                    timeout=60.0,
                )

            if response.status_code >= 400:
                print(f"  Supabase upload failed: {response.status_code} {response.text[:200]}")
                return None

            public_url = f"{supabase_url}/storage/v1/object/public/videos/{filename}"
            print(f"  uploaded related video: {file_size // 1024}KB")
            return public_url
    except Exception as exc:
        print(f"  promo video upload failed: {exc}")
        return None


def search_promo_video(search_query: str) -> str | None:
    if not search_query:
        return None

    query = search_query.strip()
    print(f"  searching related video: {query}")

    try:
        result = subprocess.run(
            ["yt-dlp", f"ytsearch5:{query}", "-j", "--no-download", "--no-warnings"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        candidates: list[tuple[int, str, str]] = []
        for line in result.stdout.strip().split("\n"):
            try:
                info = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue

            duration = info.get("duration") or 999
            video_id = info.get("id", "")
            title = info.get("title", "")
            if duration <= 60 and video_id:
                candidates.append((duration, video_id, title))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        duration, best_id, best_title = candidates[0]
        print(f"  found related short video: {best_title[:60]}... ({duration}s)")
        return _download_and_upload_video(f"https://www.youtube.com/watch?v={best_id}")
    except Exception as exc:
        print(f"  related video search failed: {exc}")
        return None


def fetch_og_image(url: str | None) -> str | None:
    if not url:
        return None
    try:
        response = httpx.get(
            url,
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if response.status_code != 200:
            return None

        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            response.text,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                response.text,
                re.IGNORECASE,
            )
        return match.group(1) if match else None
    except Exception as exc:
        print(f"  og:image extraction failed: {exc}")
        return None


def resolve_media_bundle(
    article: dict,
    media_plan: dict | None,
    media_cache: dict[str, dict[str, str]],
) -> dict[str, str]:
    raw_link = article.get("link", "")
    source_link = normalize_source_link(raw_link)
    cache_key = source_link or article.get("original_title", "") or article.get("title", "")
    if cache_key in media_cache:
        return media_cache[cache_key]

    media_plan = media_plan or {}
    if media_plan.get("reason"):
        print(f"  media rationale: {media_plan.get('reason')}")

    video_url = fetch_og_video(source_link)
    if video_url:
        print(f"  found article video: {video_url[:80]}...")

    og_image = fetch_og_image(source_link)
    if og_image:
        print(f"  found og:image: {og_image[:80]}...")

    preferred_type = str(media_plan.get("preferred_type", "video")).lower()
    search_query = str(media_plan.get("search_query", "")).strip() or article.get("original_title", "") or article.get("title", "")

    if not video_url and preferred_type != "none":
        video_url = search_promo_video(search_query)

    if not video_url and not og_image:
        print("  no related media found")

    bundle = {
        "source_link": source_link,
        "og_image": og_image or "",
        "video_url": video_url or "",
    }
    media_cache[cache_key] = bundle
    return bundle


def _build_learning_record(
    *,
    mode: str,
    candidate_articles: list[dict],
    engagement_patterns: dict | None,
    content: dict,
    qa_result,
    source_date: str,
    posted: bool,
    posting_result: dict | None = None,
) -> dict:
    return {
        "mode": mode,
        "source_date": source_date,
        "candidate_articles": candidate_articles,
        "selected_article": content.get("selected_article", {}),
        "engagement_patterns": engagement_patterns or {},
        "content": content,
        "qa": {
            "passed": qa_result.passed,
            "score": qa_result.score,
            "issues": list(qa_result.issues),
            "suggestions": list(qa_result.suggestions),
        },
        "media_plan": content.get("media_plan", {}),
        "posted": posted,
        "posting_result": posting_result or {},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Threads pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Generate and QA only, without posting")
    parser.add_argument("--collect-engagement", action="store_true", help="Collect engagement only, then exit")
    parser.add_argument(
        "--export-sft",
        default="",
        help="Export accumulated learning records as SFT-style JSONL to the given path and exit",
    )
    parser.add_argument(
        "--mode",
        choices=["viral", "informational"],
        default=None,
        help="Content mode (default comes from config.CONTENT_MODE)",
    )
    args = parser.parse_args()

    mode = args.mode or CONTENT_MODE
    print(f"[mode] {mode}")

    if args.export_sft:
        from learning_log import export_sft_examples

        output_path = Path(args.export_sft)
        examples = export_sft_examples(output_path=output_path, passed_only=True)
        print(f"[export] wrote {len(examples)} SFT examples to {output_path}")
        return

    if args.collect_engagement:
        from engagement_tracker import collect_all_engagement, save_engagement_history

        entries = collect_all_engagement()
        if entries:
            save_engagement_history(entries)
            print(f"[done] collected engagement for {len(entries)} posts")
        else:
            print("[info] no engagement data to collect")
        return

    if not ANTHROPIC_API_KEY:
        print("[error] ANTHROPIC_API_KEY is missing")
        sys.exit(1)

    if not args.dry_run and (not THREADS_ACCESS_TOKEN or not THREADS_USER_ID):
        print("[error] THREADS_ACCESS_TOKEN or THREADS_USER_ID is missing")
        sys.exit(1)

    if hasattr(signal, "SIGALRM"):
        def _timeout_handler(signum, frame):  # pragma: no cover - signal availability varies
            print(f"\n[timeout] pipeline exceeded {PIPELINE_TIMEOUT}s")
            try:
                from telegram_notify import send_preview

                send_preview({"post_main": f"[timeout] pipeline exceeded {PIPELINE_TIMEOUT}s", "mode": mode})
            except Exception:
                pass
            sys.exit(1)

        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(PIPELINE_TIMEOUT)

    if not args.dry_run:
        posts_today = count_posts_today()
        if posts_today >= MAX_DAILY_POSTS:
            print(f"[skip] already posted {posts_today} times today (limit={MAX_DAILY_POSTS})")
            return

    engagement_patterns = None
    try:
        from engagement_tracker import (
            analyze_patterns,
            collect_all_engagement,
            load_engagement_history,
            save_engagement_history,
        )

        print("[0/7] collecting historical engagement...")
        entries = collect_all_engagement()
        if entries:
            save_engagement_history(entries)
            print(f"  updated {len(entries)} posts")
        history = load_engagement_history()
        if history:
            engagement_patterns = analyze_patterns(history, mode=mode)
            print(f"  pattern analysis ready ({len(history)} rows)")
    except Exception as exc:
        print(f"  skipped engagement collection: {exc}")

    print("\n[1/7] collecting AI news from multiple sources...")
    from rss_collector import collect_news
    from social_collector import collect_social

    articles: list[dict] = []
    try:
        articles.extend(collect_social(max_count=30))
    except Exception as exc:
        print(f"  social collection failed: {exc}")

    rss_articles = collect_news(max_count=50)
    if rss_articles:
        articles.extend(rss_articles)
        print(f"  + RSS {len(rss_articles)} articles, total {len(articles)}")

    if not articles:
        print("[error] could not collect any articles")
        sys.exit(1)

    print("\n[2/7] filtering AI-related candidates...")
    from news_filter import filter_by_keywords

    filtered = filter_by_keywords(articles, max_count=15) or articles[:15]
    print(f"  {len(filtered)} candidates after keyword filtering")

    from history import filter_duplicates, load_used_titles, save_title

    before_dedup = len(filtered)
    filtered = filter_duplicates(filtered)
    if before_dedup != len(filtered):
        print(f"  removed {before_dedup - len(filtered)} recent duplicates")

    if not filtered:
        print("[error] no candidates left after deduplication")
        sys.exit(1)

    for article in filtered:
        article["candidate_score"] = score_candidate(article)
    filtered.sort(key=lambda article: article.get("candidate_score", 0), reverse=True)

    from article_enricher import enrich_articles

    filtered = enrich_articles(filtered, max_articles=5)

    if not args.dry_run:
        from ai_writer import evaluate_worthiness

        posts_today = count_posts_today()
        force = datetime.now().hour >= FORCE_POST_HOUR and posts_today == 0
        if not force:
            print("\n[2.7/7] checking whether today is worth posting...")
            worthy, reason = evaluate_worthiness(filtered, mode=mode)
            if not worthy:
                print(f"  [skip] {reason}")
                return
            print(f"  posting approved: {reason}")

    print(f"\n[3/7] generating thread ({mode})...")
    from ai_writer import generate_post
    from qa_evaluator import evaluate

    max_qa_retries = 3
    used_titles = load_used_titles()
    qa_feedback = None
    content = None
    qa_result = None
    media_bundle = {"source_link": "", "og_image": "", "video_url": ""}
    media_cache: dict[str, dict[str, str]] = {}

    for attempt in range(1, max_qa_retries + 1):
        content = generate_post(
            filtered,
            used_titles=used_titles,
            engagement_patterns=engagement_patterns,
            qa_feedback=qa_feedback,
            mode=mode,
        )
        article = content.get("selected_article", {})
        print(f"  selected: {article.get('original_title', '?')}")

        print("\n[3.5/7] resolving source link and related media...")
        media_bundle = resolve_media_bundle(article, content.get("media_plan", {}), media_cache)
        content = build_content_with_media(content, **media_bundle)

        print(f"\n[4/7] QA evaluation ({attempt}/{max_qa_retries})...")
        qa_result = evaluate(content, mode=mode)
        print(f"  score: {qa_result.score:.2f} | {'PASS' if qa_result.passed else 'FAIL'}")

        if qa_result.issues:
            for issue in qa_result.issues:
                print(f"  - {issue}")

        if qa_result.passed:
            break

        if attempt < max_qa_retries:
            qa_feedback = {
                "previous_post": content,
                "issues": qa_result.issues,
                "suggestions": qa_result.suggestions,
                "score": qa_result.score,
            }
            print("  regenerating with QA feedback...")
        else:
            print(f"  [skip] QA failed {max_qa_retries} times")
            return

    assert content is not None and qa_result is not None
    article = content.get("selected_article", {})
    source_link = media_bundle.get("source_link", content.get("source_link", ""))
    og_image = media_bundle.get("og_image", content.get("og_image", ""))
    video_url = media_bundle.get("video_url", content.get("video_url", ""))

    out_dir = Path("output") / date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    post_json_path = out_dir / "post.json"

    save_data = {
        **build_content_with_media(content, source_link=source_link, og_image=og_image, video_url=video_url),
        "mode": mode,
        "candidate_articles": filtered[:10],
        "engagement_patterns": engagement_patterns or {},
        "qa": {
            "passed": qa_result.passed,
            "score": qa_result.score,
            "issues": list(qa_result.issues),
            "suggestions": list(qa_result.suggestions),
        },
    }
    post_json_path.write_text(json.dumps(save_data, ensure_ascii=False, indent=2), encoding="utf-8")

    from telegram_notify import send_preview

    send_preview({**save_data, "mode": mode})

    from learning_log import append_learning_record

    source_date = date.today().isoformat()
    if args.dry_run:
        append_learning_record(
            _build_learning_record(
                mode=mode,
                candidate_articles=filtered[:10],
                engagement_patterns=engagement_patterns,
                content=save_data,
                qa_result=qa_result,
                source_date=source_date,
                posted=False,
            )
        )
        print("\n[dry-run] skipping Threads post")
        return

    print("\n[6/7] posting to Threads...")
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
    print("  post complete")

    save_data["posting_result"] = result
    save_data["posted_at"] = datetime.now().isoformat()
    post_json_path.write_text(json.dumps(save_data, ensure_ascii=False, indent=2), encoding="utf-8")

    if article.get("original_title"):
        save_title(article["original_title"], url=article.get("link", ""))

    append_learning_record(
        _build_learning_record(
            mode=mode,
            candidate_articles=filtered[:10],
            engagement_patterns=engagement_patterns,
            content=save_data,
            qa_result=qa_result,
            source_date=source_date,
            posted=True,
            posting_result=result,
        )
    )

    from telegram_notify import send_result

    send_result(result)


if __name__ == "__main__":
    main()
