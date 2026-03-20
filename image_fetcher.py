import base64
import io
import requests
from bs4 import BeautifulSoup
from PIL import Image
from config import PEXELS_API_KEY


def extract_og_image(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    tag = soup.find("meta", property="og:image")
    if tag and tag.get("content"):
        return tag["content"]
    return None


def extract_article_text(html_text, max_chars=500):
    """기사 본문 앞부분을 추출"""
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    paragraphs = soup.find_all("p")
    text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
    return text[:max_chars] if text else ""


def resize_to_thumbnail(image_bytes, size=120):
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def resize_to_banner(image_bytes, width=1080, height=480):
    """배너용 고해상도 이미지 (1080x480 크롭+리사이즈)"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        w, h = img.size
        target_ratio = width / height
        current_ratio = w / h
        if current_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            # 상단 기준 크롭 (인물 얼굴 보존)
            top = 0
            img = img.crop((0, top, w, top + new_h))
        img = img.resize((width, height), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def _fetch_og_image_raw(url):
    """og:image에서 원본 이미지 바이트를 가져옴"""
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        og_url = extract_og_image(resp.text)
        if not og_url:
            return None, ""
        article_text = extract_article_text(resp.text)
        img_resp = requests.get(og_url, timeout=10)
        img_resp.raise_for_status()
        return img_resp.content, article_text
    except Exception:
        return None, ""


def _fetch_og_thumbnail(url, size=120):
    raw, _ = _fetch_og_image_raw(url)
    if raw:
        return resize_to_thumbnail(raw, size)
    return None


def _fetch_pexels_image_raw(query):
    """Pexels에서 원본 이미지 바이트를 가져옴"""
    if not PEXELS_API_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": query, "per_page": 1},
            headers={"Authorization": PEXELS_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            return None
        img_url = photos[0]["src"]["landscape"]
        img_resp = requests.get(img_url, timeout=10)
        img_resp.raise_for_status()
        return img_resp.content
    except Exception:
        return None


def _fetch_pexels_thumbnail(query, size=120):
    raw = _fetch_pexels_image_raw(query)
    if raw:
        return resize_to_thumbnail(raw, size)
    return None


def fetch_thumbnail(article, size=120):
    """하위 호환용"""
    thumb, _, _ = fetch_images(article)
    return thumb


def fetch_images(article):
    """기사에서 썸네일(120px) + 배너(1080x480) + 본문 텍스트를 수집"""
    link = article.get("link", "")
    title = article.get("title", "")
    raw = None
    article_text = ""

    # 1차: og:image에서 원본 + 본문
    if link:
        raw, article_text = _fetch_og_image_raw(link)

    # 2차: Pexels 폴백
    if not raw and title:
        words = title.split()[:3]
        raw = _fetch_pexels_image_raw(" ".join(words))

    thumbnail, banner = None, None
    if raw:
        thumbnail = resize_to_thumbnail(raw, 120)
        banner = resize_to_banner(raw, 1080, 480)

    return thumbnail, banner, article_text


def fetch_all_thumbnails(articles, size=120):
    for article in articles:
        thumbnail, banner, body_text = fetch_images(article)
        article["thumbnail_b64"] = thumbnail
        article["banner_b64"] = banner
        if body_text:
            article["body"] = body_text
    return articles
