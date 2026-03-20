from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from config import (
    CARD_WIDTH, CARD_HEIGHT, BG_COLOR, TEXT_COLOR,
    ACCENT_COLOR, SUB_TEXT_COLOR, FONT_PATH, FONT_PATH_REGULAR,
)


def _load_font(size, bold=False):
    path = FONT_PATH if bold else FONT_PATH_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default(size)


def _new_card():
    return Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), BG_COLOR)


def _wrap_text(text, font, max_width, draw):
    lines = []
    current = ""
    for char in text:
        test = current + char
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width:
            lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def render_cover(title, date_str, output_dir):
    img = _new_card()
    draw = ImageDraw.Draw(img)

    # 상단 액센트 라인
    draw.rectangle([(80, 200), (200, 208)], fill=ACCENT_COLOR)

    # 제목
    font_title = _load_font(72, bold=True)
    draw.text((80, 240), title, font=font_title, fill=TEXT_COLOR)

    # 날짜
    font_date = _load_font(36)
    draw.text((80, 340), date_str, font=font_date, fill=SUB_TEXT_COLOR)

    # 하단 라인
    draw.rectangle([(80, 900), (1000, 902)], fill=ACCENT_COLOR)

    # 부제
    font_sub = _load_font(28)
    draw.text((80, 920), "이번 주 주요 AI 뉴스를 한눈에", font=font_sub, fill=SUB_TEXT_COLOR)

    path = str(output_dir / "card-01.png")
    img.save(path)
    return path


def render_news_card(card_data, card_number, output_dir):
    img = _new_card()
    draw = ImageDraw.Draw(img)
    max_text_width = CARD_WIDTH - 160

    y = 80

    # 카드 번호
    font_num = _load_font(24)
    draw.text((80, y), f"0{card_data['number']}", font=font_num, fill=ACCENT_COLOR)
    y += 50

    # 액센트 라인
    draw.rectangle([(80, y), (160, y + 4)], fill=ACCENT_COLOR)
    y += 30

    # 제목
    font_title = _load_font(48, bold=True)
    title_lines = _wrap_text(card_data["title"], font_title, max_text_width, draw)
    for line in title_lines:
        draw.text((80, y), line, font=font_title, fill=TEXT_COLOR)
        y += 60
    y += 10

    # 부제
    font_sub = _load_font(30)
    subtitle_lines = _wrap_text(card_data["subtitle"], font_sub, max_text_width, draw)
    for line in subtitle_lines:
        draw.text((80, y), line, font=font_sub, fill=SUB_TEXT_COLOR)
        y += 40
    y += 30

    # 구분선
    draw.rectangle([(80, y), (1000, y + 1)], fill="#E5E7EB")
    y += 30

    # 핵심 포인트
    font_point = _load_font(28)
    for point in card_data.get("points", []):
        draw.ellipse([(80, y + 8), (92, y + 20)], fill=ACCENT_COLOR)
        point_lines = _wrap_text(point, font_point, max_text_width - 30, draw)
        for line in point_lines:
            draw.text((110, y), line, font=font_point, fill=TEXT_COLOR)
            y += 38
        y += 10

    # 출처 (하단)
    font_source = _load_font(22)
    draw.text((80, 980), f"출처: {card_data.get('source', '')}", font=font_source, fill=SUB_TEXT_COLOR)

    path = str(output_dir / f"card-{card_number:02d}.png")
    img.save(path)
    return path


def render_closing(message, card_number, output_dir):
    img = _new_card()
    draw = ImageDraw.Draw(img)

    # 액센트 라인
    draw.rectangle([(80, 420), (200, 428)], fill=ACCENT_COLOR)

    # 메시지
    font_msg = _load_font(40, bold=True)
    draw.text((80, 460), message, font=font_msg, fill=TEXT_COLOR)

    # 하단 브랜드
    font_brand = _load_font(24)
    draw.text((80, 920), "AI Card News Generator", font=font_brand, fill=SUB_TEXT_COLOR)

    path = str(output_dir / f"card-{card_number:02d}.png")
    img.save(path)
    return path
