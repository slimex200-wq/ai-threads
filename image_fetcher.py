import base64
import io
import requests
from bs4 import BeautifulSoup
from PIL import Image
from config import UNSPLASH_ACCESS_KEY


def extract_og_image(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    tag = soup.find("meta", property="og:image")
    if tag and tag.get("content"):
        return tag["content"]
    return None


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


def _fetch_og_thumbnail(url, size=120):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        og_url = extract_og_image(resp.text)
        if not og_url:
            return None
        img_resp = requests.get(og_url, timeout=10)
        img_resp.raise_for_status()
        return resize_to_thumbnail(img_resp.content, size)
    except Exception:
        return None


def _fetch_unsplash_thumbnail(query, size=120):
    if not UNSPLASH_ACCESS_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 1},
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None
        img_url = results[0]["urls"]["small"]
        img_resp = requests.get(img_url, timeout=10)
        img_resp.raise_for_status()
        return resize_to_thumbnail(img_resp.content, size)
    except Exception:
        return None


def fetch_thumbnail(article, size=120):
    link = article.get("link", "")
    if link:
        thumb = _fetch_og_thumbnail(link, size)
        if thumb:
            return thumb

    title = article.get("title", "")
    if title:
        words = title.split()[:3]
        query = " ".join(words)
        return _fetch_unsplash_thumbnail(query, size)

    return None


def fetch_all_thumbnails(articles, size=120):
    for article in articles:
        article["thumbnail_b64"] = fetch_thumbnail(article, size)
    return articles
