import shutil
import os
from html2image import Html2Image
from pathlib import Path
from config import CARD_WIDTH, CARD_HEIGHT
from font_css import get_font_css


def _find_chrome():
    """크로스플랫폼 Chrome 경로 탐색"""
    env_path = os.environ.get("CHROME_BIN")
    if env_path:
        return env_path
    win_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if Path(win_path).exists():
        return win_path
    for name in ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]:
        found = shutil.which(name)
        if found:
            return found
    return None


chrome_path = _find_chrome()
hti_kwargs = {"size": (CARD_WIDTH, CARD_HEIGHT)}
if chrome_path:
    hti_kwargs["browser_executable"] = chrome_path

hti = Html2Image(**hti_kwargs)

COMMON_CSS = get_font_css() + """
* { margin:0; padding:0; box-sizing:border-box; }
body {
    width: 1080px; height: 1080px;
    font-family: 'Pretendard', 'Noto Sans CJK KR', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
}
"""


def _render(html, css, filename, output_dir):
    # Write full HTML file with embedded CSS (handles large base64 fonts)
    hti.output_path = str(output_dir)
    hti.screenshot(html_str=html, css_str=css, save_as=filename)
    return str(output_dir / filename)


def render_cover(title, date_str, output_dir, total_cards=4, keywords=None,
                 vol_num=None, trend_summary="", banner_b64=None):
    banner_css = ""
    banner_html_block = ""
    if banner_b64:
        banner_css = """
.cover-bg {
    position: absolute; inset: 0;
    z-index: 0;
}
.cover-bg img {
    width: 100%; height: 100%;
    object-fit: cover;
}
.cover-bg-overlay {
    position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(10,10,10,0.55) 0%, rgba(10,10,10,0.85) 50%, #0a0a0a 100%);
}
"""
        banner_html_block = f"""
<div class="cover-bg">
    <img src="data:image/jpeg;base64,{banner_b64}">
    <div class="cover-bg-overlay"></div>
</div>"""

    css = COMMON_CSS + banner_css + """
body {
    background: #0a0a0a;
    color: #fff;
    display: flex;
    flex-direction: column;
    padding: 100px;
    padding-top: 200px;
    position: relative;
}
.glow {
    position: absolute;
    top: -120px; left: 50%; transform: translateX(-50%);
    width: 500px; height: 400px;
    background: radial-gradient(ellipse, rgba(59,130,246,0.06) 0%, transparent 70%);
    pointer-events: none;
}
.border {
    position: absolute; inset: 0;
    border: 1px solid #2a2a2a;
    pointer-events: none;
}
.top-bar {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 40px;
    position: relative; z-index: 2;
}
.label {
    font-size: 22px; font-weight: 600;
    letter-spacing: 5px; color: #888;
}
.vol {
    font-size: 20px; font-weight: 600;
    color: #3B82F6; letter-spacing: 2px;
}
.title {
    font-size: 80px; font-weight: 900;
    line-height: 1.1; letter-spacing: -3px;
    margin-bottom: 24px;
    word-break: keep-all;
    position: relative; z-index: 2;
}
.trend {
    font-size: 26px; color: #888;
    margin-bottom: 20px;
    font-weight: 400;
    position: relative; z-index: 2;
}
.sep {
    width: 50px; height: 2px;
    background: #3B82F6; margin-bottom: 20px;
    position: relative; z-index: 2;
}
.date {
    font-size: 26px; color: #666; font-weight: 500;
    position: relative; z-index: 2;
}
.keywords {
    display: flex; gap: 12px; flex-wrap: wrap;
    margin-top: 28px;
    position: relative; z-index: 2;
}
.keyword {
    font-size: 20px; color: #3B82F6;
    padding: 8px 18px;
    border: 1px solid #1E3A5F;
    border-radius: 20px;
}
.bottom {
    position: fixed;
    bottom: 40px; left: 100px; right: 100px;
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
    vol_html = f'<span class="vol">VOL.{vol_num:02d}</span>' if vol_num else ""
    keywords_html = ""
    if keywords:
        tags = "".join(f'<span class="keyword">#{k}</span>' for k in keywords)
        keywords_html = f'<div class="keywords">{tags}</div>'
    trend_html = f'<div class="trend">{trend_summary}</div>' if trend_summary else ""

    html = f"""
{banner_html_block}
<div class="glow"></div>
<div class="border"></div>
<div class="top-bar">
    <span class="label">AI WEEKLY</span>
    {vol_html}
</div>
<div class="title">{title}</div>
{trend_html}
<div class="sep"></div>
<div class="date">{date_str}</div>
{keywords_html}
<div class="bottom">
    <span class="bottom-text">{total_cards}편의 뉴스</span>
    <div class="arrow-circle">↓</div>
</div>
"""
    return _render(html, css, "card-01.png", output_dir)


def render_news_card(card_data, card_number, output_dir, total_cards=4):
    import re as _re

    num = card_data.get("number", card_number - 1)
    source = card_data.get("source", "")
    title = card_data.get("title", "")
    subtitle = card_data.get("subtitle", "")
    points = card_data.get("points", [])
    insight = card_data.get("insight", "")
    link = card_data.get("link", "")

    # 배너 이미지 (banner_b64 우선, thumbnail_b64 폴백)
    banner_b64 = card_data.get("banner_b64") or card_data.get("thumbnail_b64")
    img_format = "jpeg" if card_data.get("banner_b64") else "png"
    banner_html = ""
    if banner_b64:
        banner_html = f"""
        <div class="banner">
            <img src="data:image/{img_format};base64,{banner_b64}">
            <div class="banner-overlay"></div>
            <div class="banner-meta">
                <span class="banner-num">{num:02d} / {total_cards:02d}</span>
                <span class="banner-source">{source}</span>
            </div>
        </div>"""
    else:
        banner_html = f"""
        <div class="banner banner-no-img">
            <div class="banner-meta">
                <span class="banner-num">{num:02d} / {total_cards:02d}</span>
                <span class="banner-source">{source}</span>
            </div>
        </div>"""

    points_html = ""
    for p in points:
        points_html += f"""
        <div class="point">
            <div class="dot"></div>
            <span>{p}</span>
        </div>"""

    # 에디터 인사이트
    insight_html = ""
    if insight:
        insight_html = f"""
        <div class="insight">
            <span class="insight-label">INSIGHT</span>
            <span class="insight-text">「{insight}」</span>
        </div>"""

    # 원문 링크
    link_html = ""
    if link:
        domain = _re.sub(r'^https?://(www\\.)?', '', link).split('/')[0]
        link_html = f'<span class="source-link">🔗 {domain}</span>'

    # page dots
    total_pages = total_cards + 2
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
    position: relative;
}
.banner {
    position: relative;
    width: 100%; height: 300px;
    flex-shrink: 0;
    overflow: hidden;
}
.banner img {
    width: 100%; height: 100%;
    object-fit: cover;
}
.banner-overlay {
    position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(10,15,30,0.15) 0%, rgba(10,10,10,0.88) 100%);
}
.banner-no-img {
    background: linear-gradient(135deg, #111 0%, #0a0a0a 100%);
}
.banner-meta {
    position: absolute; bottom: 24px; left: 72px;
    display: flex; gap: 20px; align-items: center;
}
.banner-num {
    font-size: 18px; color: rgba(255,255,255,0.7);
    font-weight: 600; letter-spacing: 2px;
}
.banner-source {
    font-size: 18px; color: rgba(255,255,255,0.5); font-weight: 500;
}
.content {
    padding: 28px 72px 0;
}
.title {
    font-size: 58px; font-weight: 900;
    line-height: 1.15; letter-spacing: -2px;
    margin-bottom: 10px;
    word-break: keep-all;
    overflow-wrap: break-word;
}
.subtitle {
    font-size: 24px; color: #888;
    margin-bottom: 28px; font-weight: 400;
}
.sep {
    width: 100%; height: 1px;
    background: #222; margin-bottom: 24px;
}
.points {
    display: flex; flex-direction: column;
    gap: 12px;
}
.point {
    display: flex; align-items: flex-start; gap: 14px;
}
.point .dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: #3B82F6; flex-shrink: 0;
    margin-top: 11px;
}
.point span {
    color: #ccc; font-size: 25px; line-height: 1.45;
}
.insight {
    margin-top: 20px; padding: 16px 20px;
    background: #111;
    border-left: 3px solid #3B82F6;
    border-radius: 0 8px 8px 0;
    display: flex; align-items: center; gap: 14px;
}
.insight-label {
    font-size: 13px; font-weight: 700;
    color: #3B82F6; letter-spacing: 2px;
    flex-shrink: 0;
}
.insight-text {
    font-size: 21px; color: #aaa;
    font-weight: 500;
}
.footer {
    position: fixed;
    bottom: 32px; left: 72px; right: 72px;
    display: flex; justify-content: space-between; align-items: center;
}
.source-link {
    font-size: 20px; color: #666;
}
.page-dots {
    display: flex; gap: 8px;
}
.dot-active {
    width: 22px; height: 8px;
    border-radius: 4px; background: #3B82F6;
}
.dot-inactive {
    width: 8px; height: 8px;
    border-radius: 50%; background: #333;
}
"""
    html = f"""
{banner_html}
<div class="content">
    <div class="title">{title}</div>
    <div class="subtitle">{subtitle}</div>
    <div class="sep"></div>
    <div class="points">{points_html}</div>
    {insight_html}
</div>
<div class="footer">
    {link_html}
    <div class="page-dots">{dots_html}</div>
</div>
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
    margin-bottom: 48px;
}
.cta {
    display: flex; flex-direction: column;
    gap: 14px; align-items: center;
}
.cta-item {
    font-size: 22px; color: #666;
    letter-spacing: 1px;
}
.cta-highlight {
    font-size: 24px; color: #3B82F6;
    font-weight: 600;
    padding: 14px 40px;
    border: 1.5px solid #3B82F6;
    border-radius: 28px;
    margin-top: 12px;
}
.cta-handle {
    font-size: 26px; color: #3B82F6;
    font-weight: 600;
    margin-top: 16px;
    letter-spacing: 1px;
}
"""
    html = f"""
<div class="border"></div>
<div class="glow"></div>
<div class="message">{message}</div>
<div class="sep"></div>
<div class="brand">AI Weekly</div>
<div class="cta">
    <span class="cta-item">매일 오전 8시, AI 뉴스 업데이트</span>
    <span class="cta-highlight">팔로우 &amp; 저장</span>
    <span class="cta-handle">@hype.boyo</span>
</div>
"""
    return _render(html, css, f"card-{card_number:02d}.png", output_dir)
