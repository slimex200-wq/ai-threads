import argparse
import sys
from config import DEFAULT_COUNT, get_output_dir, ANTHROPIC_API_KEY
from rss_collector import collect_news
from ai_writer import generate_card_content
from card_renderer import render_cover, render_news_card, render_closing


def main():
    parser = argparse.ArgumentParser(description="AI 카드뉴스 생성기")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="수집할 뉴스 개수 (기본: 4)")
    parser.add_argument("--output", type=str, default=None, help="출력 경로")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("[에러] ANTHROPIC_API_KEY 환경변수를 설정해주세요.")
        sys.exit(1)

    # 1. RSS 뉴스 수집
    print(f"[1/3] AI 뉴스 수집 중... (최대 {args.count}개)")
    articles = collect_news(max_count=args.count)
    if not articles:
        print("[에러] 뉴스를 수집하지 못했습니다.")
        sys.exit(1)
    print(f"  → {len(articles)}개 기사 수집 완료")

    # 2. Claude API로 카드 문구 생성
    print("[2/3] 카드 문구 생성 중... (Claude API)")
    content = generate_card_content(articles)
    print(f"  → {len(content['cards'])}개 카드 문구 생성 완료")

    # 3. 이미지 생성
    print("[3/3] 카드 이미지 생성 중...")
    output_dir = get_output_dir(args.output)
    generated = []

    # 표지
    path = render_cover(content["cover_title"], content["cover_date"], output_dir)
    generated.append(path)
    print(f"  → 표지: {path}")

    # 뉴스 카드
    for i, card in enumerate(content["cards"], 2):
        path = render_news_card(card, i, output_dir)
        generated.append(path)
        print(f"  → 카드 {i}: {path}")

    # 마무리
    closing_num = len(content["cards"]) + 2
    path = render_closing(content["closing_message"], closing_num, output_dir)
    generated.append(path)
    print(f"  → 마무리: {path}")

    print(f"\n완료! {len(generated)}장의 카드뉴스가 생성되었습니다.")
    print(f"저장 위치: {output_dir}")


if __name__ == "__main__":
    main()
