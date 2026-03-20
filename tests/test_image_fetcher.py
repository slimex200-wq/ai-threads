import base64
from image_fetcher import extract_og_image, resize_to_thumbnail, fetch_thumbnail


def test_extract_og_image_from_html():
    html = '<html><head><meta property="og:image" content="https://example.com/img.jpg"></head></html>'
    result = extract_og_image(html)
    assert result == "https://example.com/img.jpg"


def test_extract_og_image_missing():
    html = "<html><head><title>No image</title></head></html>"
    result = extract_og_image(html)
    assert result is None


def test_resize_to_thumbnail():
    from PIL import Image
    import io
    img = Image.new("RGB", (500, 500), "red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    result = resize_to_thumbnail(img_bytes, size=120)
    assert result is not None
    decoded = base64.b64decode(result)
    assert len(decoded) > 0


def test_resize_to_thumbnail_invalid_data():
    result = resize_to_thumbnail(b"not an image", size=120)
    assert result is None


def test_fetch_thumbnail_returns_none_on_failure():
    article = {"link": "https://invalid.example.com/nonexistent", "title": "Test"}
    result = fetch_thumbnail(article)
    assert result is None
