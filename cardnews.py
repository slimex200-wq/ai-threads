import argparse
import sys
from pathlib import Path
from config import DEFAULT_COUNT, get_output_dir, ANTHROPIC_API_KEY
from rss_collector import collect_news
from news_filter import filter_by_keywords
from image_fetcher import fetch_all_thumbnails
from ai_writer import generate_card_content
from card_renderer import render_cover, render_news_card, render_closing


def _get_volume_number(output_base):
    """output 폴더 내 날짜 디렉토리 수로 회차 계산"""
    base = Path(output_base) if output_base else Path("output")
    if not base.exists():
        return 1
    date_dirs = [d for d in base.iterdir() if d.is_dir() and len(d.name) == 10]
    return len(date_dirs) + 1


def main():
    parser = argparse.ArgumentParser(description="AI 카드뉴스 생성기")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="최종 카드 개수 (기본: 4)")
    parser.add_argument("--output", type=str, default=None, help="출력 경로")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("[에러] ANTHROPIC_API_KEY 환경변수를 설정해주세요.")
        sys.exit(1)

    # 1. RSS 뉴스 수집
    print("[1/5] AI 뉴스 수집 중...")
    articles = collect_news(max_count=50)
    if not articles:
        print("[에러] 뉴스를 수집하지 못했습니다.")
        sys.exit(1)
    print(f"  → {len(articles)}개 기사 수집")

    # 2. 키워드 필터링
    print("[2/5] AI 관련 기사 필터링 중...")
    filtered = filter_by_keywords(articles, max_count=10)
    if not filtered:
        print("  → 키워드 매칭 없음, 최신순으로 대체")
        filtered = articles[:10]
    print(f"  → {len(filtered)}개 기사 통과")

    # 3. 썸네일 + 배너 + 본문 수집
    print("[3/5] 기사 이미지 및 본문 수집 중...")
    filtered = fetch_all_thumbnails(filtered)
    thumb_count = sum(1 for a in filtered if a.get("banner_b64"))
    body_count = sum(1 for a in filtered if a.get("body"))
    print(f"  → {thumb_count}개 이미지, {body_count}개 본문 수집")

    # 4. Claude API로 선별 + 카드 문구 생성
    print("[4/5] 카드 문구 생성 중... (Claude API)")
    content = generate_card_content(filtered, select_count=args.count)
    print(f"  → {len(content['cards'])}개 카드 문구 생성 완료")

    # Claude가 선별한 카드에 이미지 + 링크 매칭 (original_title 기반)
    title_to_article = {a["title"]: a for a in filtered}
    for card in content["cards"]:
        matched = None
        # 1차: original_title로 정확 매칭
        orig_title = card.get("original_title", "")
        if orig_title and orig_title in title_to_article:
            matched = title_to_article[orig_title]
        # 2차: number 기반 폴백
        if not matched:
            idx = card.get("number", 0) - 1
            if 0 <= idx < len(filtered):
                matched = filtered[idx]
        if matched:
            if matched.get("thumbnail_b64"):
                card["thumbnail_b64"] = matched["thumbnail_b64"]
            if matched.get("banner_b64"):
                card["banner_b64"] = matched["banner_b64"]
            if not card.get("link") and matched.get("link"):
                card["link"] = matched["link"]

    # 5. 이미지 생성
    print("[5/5] 카드 이미지 생성 중...")
    output_dir = get_output_dir(args.output)
    generated = []
    total_cards = len(content["cards"])

    # 회차 번호
    vol_num = _get_volume_number(args.output)

    # 표지용 키워드 수집
    all_keywords = []
    for card in content["cards"]:
        all_keywords.extend(card.get("keywords", []))
    seen = set()
    unique_keywords = []
    for kw in all_keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)
    cover_keywords = unique_keywords[:4]

    # 표지: 동적 헤드라인 + 트렌드 서사
    cover_headline = content.get("cover_headline", "이번 주 AI 뉴스")
    trend_summary = content.get("trend_summary", "")

    # 표지 배너: 첫 번째 카드의 배너 사용
    cover_banner = None
    for card in content["cards"]:
        if card.get("banner_b64"):
            cover_banner = card["banner_b64"]
            break

    path = render_cover(
        cover_headline, content["cover_date"], output_dir, total_cards,
        keywords=cover_keywords, vol_num=vol_num, trend_summary=trend_summary,
        banner_b64=cover_banner,
    )
    generated.append(path)
    print(f"  → 표지: card-01.png")

    for i, card in enumerate(content["cards"], 2):
        path = render_news_card(card, i, output_dir, total_cards)
        generated.append(path)
        print(f"  → 카드 {i}: card-{i:02d}.png")

    closing_num = total_cards + 2
    path = render_closing(content["closing_message"], closing_num, output_dir, total_cards)
    generated.append(path)
    print(f"  → 마무리: card-{closing_num:02d}.png")

    # 스레드 1: 캡션 (요약 + 해시태그)
    caption = content.get("caption", "")
    if caption:
        (output_dir / "caption.txt").write_text(caption, encoding="utf-8")
        print(f"  → 캡션: caption.txt")

    # 스레드 2: 원문 링크 (타래용)
    links = []
    for card in content["cards"]:
        link = card.get("link", "")
        if link:
            links.append(f"🔗 {link}")
    if links:
        links_text = "원문 링크:\n" + "\n".join(links)
        (output_dir / "links.txt").write_text(links_text, encoding="utf-8")
        print(f"  → 링크: links.txt")

    print(f"\n완료! {len(generated)}장의 카드뉴스가 생성되었습니다.")
    print(f"저장 위치: {output_dir}")


if __name__ == "__main__":
    main()
