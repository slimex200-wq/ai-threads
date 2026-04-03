"""Threads Insights API를 통한 포스트 성과 수집 모듈.

포스팅 24시간 이후 Insights API로 지표를 수집하여
output/performance.jsonl에 기록한다.

Usage:
    python performance_tracker.py              # 미수집 포스트 전체 수집
    python performance_tracker.py --days 3     # 최근 3일만 수집
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from config import THREADS_ACCESS_TOKEN, THREADS_USER_ID

GRAPH_API_BASE = "https://graph.threads.net/v1.0"
OUTPUT_DIR = Path("output")
PERFORMANCE_FILE = OUTPUT_DIR / "performance.jsonl"
DEFAULT_LOOKBACK_DAYS = 7

INSIGHT_METRICS = "views,likes,replies,reposts,quotes"


# ---------------------------------------------------------------------------
# Data classes (frozen — immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PostContent:
    """포스트 내용 요약."""

    post_main: str
    reply_texts: tuple[str, ...]
    selected_article: dict[str, Any]


@dataclass(frozen=True)
class PostMetrics:
    """Insights API에서 수집한 지표."""

    views: int = 0
    likes: int = 0
    replies: int = 0
    reposts: int = 0
    quotes: int = 0


@dataclass(frozen=True)
class PerformanceRecord:
    """성과 수집 결과 한 건."""

    post_id: str
    posted_date: str
    collected_at: str
    content: dict[str, Any]
    metrics: dict[str, int]
    engagement_rate: float
    qa_score: float | None


# ---------------------------------------------------------------------------
# Insights API
# ---------------------------------------------------------------------------


def _fetch_insights(
    client: httpx.Client,
    media_id: str,
    access_token: str,
) -> PostMetrics:
    """Threads Insights API에서 지표를 가져온다.

    Raises:
        RuntimeError: API 호출 실패 시 (토큰 만료, 레이트 리밋 등)
    """
    url = f"{GRAPH_API_BASE}/{media_id}/insights"
    params = {"metric": INSIGHT_METRICS, "access_token": access_token}

    resp = client.get(url, params=params)

    if resp.status_code == 401:
        raise RuntimeError(
            f"[인사이트] 인증 실패 (토큰 만료 가능): {resp.status_code} {resp.text[:300]}"
        )
    if resp.status_code == 429:
        raise RuntimeError(
            f"[인사이트] 레이트 리밋 초과: {resp.status_code} {resp.text[:300]}"
        )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"[인사이트] API 에러: {resp.status_code} {resp.text[:300]}"
        )

    data = resp.json().get("data", [])
    values: dict[str, int] = {}
    for item in data:
        name = item.get("name", "")
        # Insights API returns values as a list with one dict
        item_values = item.get("values", [])
        if item_values:
            values[name] = int(item_values[0].get("value", 0))
        else:
            values[name] = int(item.get("total_value", {}).get("value", 0))

    return PostMetrics(
        views=values.get("views", 0),
        likes=values.get("likes", 0),
        replies=values.get("replies", 0),
        reposts=values.get("reposts", 0),
        quotes=values.get("quotes", 0),
    )


# ---------------------------------------------------------------------------
# post.json 로딩
# ---------------------------------------------------------------------------


def _extract_reply_texts(post_data: dict[str, Any]) -> tuple[str, ...]:
    """post.json에서 대댓글 텍스트를 추출한다."""
    reply_keys = (
        "reply_explain",
        "reply_important",
        "reply_action",
        "reply_counter",
        "reply_casual",
    )
    return tuple(
        post_data[key] for key in reply_keys if key in post_data and post_data[key]
    )


def _load_post_data(post_json_path: Path) -> dict[str, Any] | None:
    """post.json 파일을 읽어 dict로 반환한다. 실패 시 None."""
    try:
        text = post_json_path.read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[경고] {post_json_path} 읽기 실패: {e}")
        return None


def load_recent_posts(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> list[tuple[str, dict[str, Any]]]:
    """최근 N일간의 post.json을 (날짜문자열, 데이터) 튜플 리스트로 반환한다.

    post_id가 없는 포스트는 건너뛴다.
    """
    today = date.today()
    results: list[tuple[str, dict[str, Any]]] = []

    for offset in range(lookback_days):
        target_date = today - timedelta(days=offset)
        date_str = target_date.isoformat()
        post_path = OUTPUT_DIR / date_str / "post.json"

        if not post_path.exists():
            continue

        data = _load_post_data(post_path)
        if data is None:
            continue

        if not data.get("post_id"):
            print(f"[건너뜀] {date_str}: post_id 없음 (미포스팅 또는 dry-run)")
            continue

        results.append((date_str, data))

    return results


# ---------------------------------------------------------------------------
# 수집 완료 여부 확인
# ---------------------------------------------------------------------------


def _load_collected_post_ids() -> frozenset[str]:
    """performance.jsonl에서 이미 수집된 post_id 목록을 반환한다."""
    if not PERFORMANCE_FILE.exists():
        return frozenset()

    collected: set[str] = set()
    try:
        lines = PERFORMANCE_FILE.read_text(encoding="utf-8").splitlines()
        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
                pid = record.get("post_id", "")
                if pid:
                    collected.add(pid)
            except json.JSONDecodeError as e:
                print(f"[경고] performance.jsonl 줄 {line_num} 파싱 실패: {e}")
    except OSError as e:
        print(f"[경고] performance.jsonl 읽기 실패: {e}")

    return frozenset(collected)


# ---------------------------------------------------------------------------
# engagement_rate 계산
# ---------------------------------------------------------------------------


def _calc_engagement_rate(metrics: PostMetrics) -> float:
    """(replies + likes) / max(views, 1)"""
    return (metrics.replies + metrics.likes) / max(metrics.views, 1)


# ---------------------------------------------------------------------------
# 수집 메인
# ---------------------------------------------------------------------------


def _build_record(
    post_id: str,
    posted_date: str,
    post_data: dict[str, Any],
    metrics: PostMetrics,
) -> PerformanceRecord:
    """수집 결과를 PerformanceRecord로 조립한다."""
    content = {
        "post_main": post_data.get("post_main", ""),
        "reply_texts": list(_extract_reply_texts(post_data)),
        "selected_article": post_data.get("selected_article", {}),
    }

    return PerformanceRecord(
        post_id=post_id,
        posted_date=posted_date,
        collected_at=datetime.now().isoformat(timespec="seconds"),
        content=content,
        metrics=asdict(metrics),
        engagement_rate=round(_calc_engagement_rate(metrics), 6),
        qa_score=post_data.get("qa_score"),
    )


def _append_record(record: PerformanceRecord) -> None:
    """performance.jsonl에 레코드 한 줄을 추가한다."""
    PERFORMANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PERFORMANCE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def collect_all(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> list[PerformanceRecord]:
    """미수집 포스트의 Insights를 수집하여 performance.jsonl에 추가한다.

    Returns:
        새로 수집된 PerformanceRecord 리스트
    """
    if not THREADS_ACCESS_TOKEN:
        print("[에러] THREADS_ACCESS_TOKEN 미설정")
        return []

    posts = load_recent_posts(lookback_days)
    if not posts:
        print("[정보] 수집 대상 포스트가 없습니다.")
        return []

    collected_ids = _load_collected_post_ids()
    uncollected = [
        (d, data) for d, data in posts if data["post_id"] not in collected_ids
    ]

    if not uncollected:
        print("[정보] 모든 포스트가 이미 수집되었습니다.")
        return []

    print(f"[수집] {len(uncollected)}개 포스트 인사이트 수집 시작...")
    new_records: list[PerformanceRecord] = []

    with httpx.Client(timeout=30.0) as client:
        for posted_date, post_data in uncollected:
            post_id = post_data["post_id"]
            print(f"  {posted_date} (ID: {post_id})...", end=" ")

            try:
                metrics = _fetch_insights(client, post_id, THREADS_ACCESS_TOKEN)
            except RuntimeError as e:
                print(f"실패: {e}")
                continue

            record = _build_record(post_id, posted_date, post_data, metrics)
            _append_record(record)
            new_records.append(record)

            print(
                f"완료 (views={metrics.views}, likes={metrics.likes}, "
                f"engagement={record.engagement_rate:.4f})"
            )

    print(f"[완료] {len(new_records)}개 수집 완료")
    return new_records


# ---------------------------------------------------------------------------
# Top / Worst 분석
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RankedPost:
    """순위가 매겨진 포스트."""

    post_id: str
    posted_date: str
    engagement_rate: float
    metrics: dict[str, int]
    content_summary: str  # post_main 앞 80자


@dataclass(frozen=True)
class TopWorstResult:
    """상위/하위 포스트 분석 결과."""

    top: tuple[RankedPost, ...]
    worst: tuple[RankedPost, ...]


def _load_all_records() -> list[dict[str, Any]]:
    """performance.jsonl의 모든 레코드를 읽는다."""
    if not PERFORMANCE_FILE.exists():
        return []

    records: list[dict[str, Any]] = []
    lines = PERFORMANCE_FILE.read_text(encoding="utf-8").splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue

    return records


def get_top_and_worst(n: int = 3) -> TopWorstResult:
    """engagement_rate 기준 상위 N개, 하위 N개 포스트를 반환한다.

    ai_writer.py에서 과거 성과 참고용으로 사용 가능.
    """
    records = _load_all_records()
    if not records:
        return TopWorstResult(top=(), worst=())

    # engagement_rate 내림차순 정렬 (새 리스트 — 원본 불변)
    sorted_records = sorted(
        records, key=lambda r: r.get("engagement_rate", 0), reverse=True
    )

    def _to_ranked(record: dict[str, Any]) -> RankedPost:
        content = record.get("content", {})
        post_main = content.get("post_main", "")
        summary = post_main[:80] + ("..." if len(post_main) > 80 else "")
        return RankedPost(
            post_id=record.get("post_id", ""),
            posted_date=record.get("posted_date", ""),
            engagement_rate=record.get("engagement_rate", 0.0),
            metrics=record.get("metrics", {}),
            content_summary=summary,
        )

    top = tuple(_to_ranked(r) for r in sorted_records[:n])
    worst = tuple(_to_ranked(r) for r in sorted_records[-n:])

    # 데이터가 n개 이하면 top과 worst가 겹칠 수 있으므로 중복 제거
    if len(sorted_records) <= n:
        return TopWorstResult(top=top, worst=())

    return TopWorstResult(top=top, worst=worst)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_top_worst(result: TopWorstResult) -> None:
    """Top/Worst 결과를 콘솔에 출력한다."""
    if result.top:
        print("\n--- Top 포스트 (engagement_rate 높은 순) ---")
        for i, post in enumerate(result.top, start=1):
            print(
                f"  {i}. [{post.posted_date}] "
                f"engagement={post.engagement_rate:.4f} "
                f"views={post.metrics.get('views', 0)} "
                f"likes={post.metrics.get('likes', 0)}"
            )
            print(f"     {post.content_summary}")

    if result.worst:
        print("\n--- Worst 포스트 (engagement_rate 낮은 순) ---")
        for i, post in enumerate(result.worst, start=1):
            print(
                f"  {i}. [{post.posted_date}] "
                f"engagement={post.engagement_rate:.4f} "
                f"views={post.metrics.get('views', 0)} "
                f"likes={post.metrics.get('likes', 0)}"
            )
            print(f"     {post.content_summary}")


def main() -> None:
    """CLI 진입점 — 미수집 포스트 인사이트 수집 후 Top/Worst 출력."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Threads 포스트 성과 수집 (Insights API)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help=f"최근 N일 포스트 대상 (기본: {DEFAULT_LOOKBACK_DAYS})",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=3,
        help="Top/Worst 표시 개수 (기본: 3)",
    )
    args = parser.parse_args()

    if not THREADS_ACCESS_TOKEN:
        print("[에러] THREADS_ACCESS_TOKEN 환경변수를 설정하세요.")
        sys.exit(1)

    new_records = collect_all(lookback_days=args.days)

    # 수집 결과와 관계없이 기존 데이터 포함 Top/Worst 출력
    result = get_top_and_worst(n=args.top)
    _print_top_worst(result)


if __name__ == "__main__":
    main()
