import argparse
import sys
from config import DEFAULT_COUNT, get_output_dir, ANTHROPIC_API_KEY
from rss_collector import collect_news
from news_filter import filter_by_keywords
from image_fetcher import fetch_all_thumbnails
from ai_writer import generate_card_content
from card_renderer import render_cover, render_news_card, render_closing


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

    # 3. 썸네일 이미지 수집
    print("[3/5] 기사 썸네일 수집 중...")
    filtered = fetch_all_thumbnails(filtered)
    thumb_count = sum(1 for a in filtered if a.get("thumbnail_b64"))
    print(f"  → {thumb_count}개 썸네일 수집")

    # 4. Claude API로 선별 + 카드 문구 생성
    print("[4/5] 카드 문구 생성 중... (Claude API)")
    content = generate_card_content(filtered, select_count=args.count)
    print(f"  → {len(content['cards'])}개 카드 문구 생성 완료")

    # Claude가 선별한 카드에 썸네일 매칭
    filtered_by_source = {a.get("source", ""): a for a in filtered}
    for card in content["cards"]:
        source = card.get("source", "")
        matched = filtered_by_source.get(source)
        if matched and matched.get("thumbnail_b64"):
            card["thumbnail_b64"] = matched["thumbnail_b64"]

    # 5. 이미지 생성
    print("[5/5] 카드 이미지 생성 중...")
    output_dir = get_output_dir(args.output)
    generated = []

    total_cards = len(content["cards"])

    path = render_cover(content["cover_title"], content["cover_date"], output_dir, total_cards)
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

    print(f"\n완료! {len(generated)}장의 카드뉴스가 생성되었습니다.")
    print(f"저장 위치: {output_dir}")


if __name__ == "__main__":
    main()
