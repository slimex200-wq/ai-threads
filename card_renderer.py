from html2image import Html2Image
from pathlib import Path
from config import CARD_WIDTH, CARD_HEIGHT

hti = Html2Image(
    browser_executable=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    size=(CARD_WIDTH, CARD_HEIGHT),
)

COMMON_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body {
    width: 1080px; height: 1080px;
    font-family: 'Pretendard', sans-serif;
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
}
"""


def _render(html, css, filename, output_dir):
    # Write full HTML file with embedded CSS (handles large base64 fonts)
    hti.output_path = str(output_dir)
    hti.screenshot(html_str=html, css_str=css, save_as=filename)
    return str(output_dir / filename)


def render_cover(title, date_str, output_dir, total_cards=4):
    css = COMMON_CSS + """
body {
    background: #0a0a0a;
    color: #fff;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 100px;
    position: relative;
}
.glow {
    position: absolute;
    top: -120px; left: 50%; transform: translateX(-50%);
    width: 500px; height: 400px;
    background: radial-gradient(ellipse, rgba(255,255,255,0.04) 0%, transparent 70%);
    pointer-events: none;
}
.border {
    position: absolute; inset: 0;
    border: 1px solid #2a2a2a;
    pointer-events: none;
}
.label {
    font-size: 22px; font-weight: 600;
    letter-spacing: 5px; color: #888;
    margin-bottom: 28px;
}
.title {
    font-size: 110px; font-weight: 900;
    line-height: 1.05; letter-spacing: -4px;
    margin-bottom: 20px;
}
.sep {
    width: 50px; height: 1px;
    background: #444; margin-bottom: 20px;
}
.date {
    font-size: 28px; color: #666; font-weight: 500;
}
.bottom {
    position: absolute;
    bottom: 48px; left: 100px; right: 100px;
    display: flex; justify-content: space-between; align-items: center;
}
.bottom-text { font-size: 24px; color: #555; }
.arrow-circle {
    width: 40px; height: 40px;
    border: 1px solid #444; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; color: #888;
}
"""
    html = f"""
<div class="glow"></div>
<div class="border"></div>
<div class="label">AI WEEKLY</div>
<div class="title">이번 주<br>AI 뉴스</div>
<div class="sep"></div>
<div class="date">{date_str}</div>
<div class="bottom">
    <span class="bottom-text">{total_cards}편의 뉴스</span>
    <div class="arrow-circle">↓</div>
</div>
"""
    return _render(html, css, "card-01.png", output_dir)


def render_news_card(card_data, card_number, output_dir, total_cards=4):
    num = card_data.get("number", card_number - 1)
    source = card_data.get("source", "")
    title = card_data.get("title", "")
    subtitle = card_data.get("subtitle", "")
    points = card_data.get("points", [])

    points_html = ""
    for p in points:
        points_html += f"""
        <div class="point">
            <div class="dot"></div>
            <span>{p}</span>
        </div>"""

    # page dots
    total_pages = total_cards + 2  # cover + news cards + closing
    dots_html = ""
    for i in range(total_pages):
        if i == card_number - 1:
            dots_html += '<div class="dot-active"></div>'
        else:
            dots_html += '<div class="dot-inactive"></div>'

    css = COMMON_CSS + """
body {
    background: #0a0a0a;
    color: #fff;
    padding: 100px;
    position: relative;
    display: flex;
    flex-direction: column;
}
.border {
    position: absolute; inset: 0;
    border: 1px solid #2a2a2a;
    pointer-events: none;
}
.top-line {
    position: absolute; top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, #444, transparent);
}
.header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 60px;
}
.header-num {
    font-size: 22px; color: #888;
    font-weight: 600; letter-spacing: 2px;
}
.header-source {
    font-size: 22px; color: #666; font-weight: 500;
}
.title {
    font-size: 68px; font-weight: 900;
    line-height: 1.15; letter-spacing: -2px;
    margin-bottom: 14px;
    word-break: keep-all;
    overflow-wrap: break-word;
}
.subtitle {
    font-size: 30px; color: #777;
    margin-bottom: 40px; font-weight: 400;
}
.sep {
    width: 100%; height: 1px;
    background: #222; margin-bottom: 36px;
}
.points {
    display: flex; flex-direction: column;
    gap: 18px; flex: 1;
}
.point {
    display: flex; align-items: center; gap: 16px;
}
.point .dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: #fff; flex-shrink: 0;
}
.point span {
    color: #bbb; font-size: 28px;
}
.page-dots {
    display: flex; gap: 8px;
    justify-content: center;
    padding-top: 32px;
    margin-top: auto;
}
.dot-active {
    width: 22px; height: 8px;
    border-radius: 4px; background: #fff;
}
.dot-inactive {
    width: 8px; height: 8px;
    border-radius: 50%; background: #333;
}
"""
    html = f"""
<div class="border"></div>
<div class="top-line"></div>
<div class="header">
    <span class="header-num">{num:02d} / {total_cards:02d}</span>
    <span class="header-source">{source}</span>
</div>
<div class="title">{title}</div>
<div class="subtitle">{subtitle}</div>
<div class="sep"></div>
<div class="points">{points_html}</div>
<div class="page-dots">{dots_html}</div>
"""
    return _render(html, css, f"card-{card_number:02d}.png", output_dir)


def render_closing(message, card_number, output_dir, total_cards=4):
    css = COMMON_CSS + """
body {
    background: #0a0a0a;
    color: #fff;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    position: relative;
}
.border {
    position: absolute; inset: 0;
    border: 1px solid #2a2a2a;
    pointer-events: none;
}
.glow {
    position: absolute;
    top: 50%; left: 50%; transform: translate(-50%, -50%);
    width: 450px; height: 450px;
    background: radial-gradient(circle, rgba(255,255,255,0.03) 0%, transparent 70%);
    pointer-events: none;
}
.message {
    font-size: 72px; font-weight: 900;
    letter-spacing: -2px;
    margin-bottom: 20px;
}
.sep {
    width: 50px; height: 1px;
    background: #333; margin-bottom: 24px;
}
.brand {
    font-size: 24px; color: #444;
}
"""
    html = f"""
<div class="border"></div>
<div class="glow"></div>
<div class="message">{message}</div>
<div class="sep"></div>
<div class="brand">AI Weekly</div>
"""
    return _render(html, css, f"card-{card_number:02d}.png", output_dir)
