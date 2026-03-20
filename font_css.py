"""Generate @font-face CSS with base64-embedded Pretendard fonts."""
import base64
from pathlib import Path

FONT_DIR = Path(__file__).parent / "fonts"

_WEIGHTS = {
    400: "Regular",
    500: "Medium",
    600: "SemiBold",
    700: "Bold",
    800: "ExtraBold",
    900: "Black",
}

_cache = None

def get_font_css():
    global _cache
    if _cache:
        return _cache

    parts = []
    for weight, variant in _WEIGHTS.items():
        font_path = FONT_DIR / f"Pretendard-{variant}.woff2"
        b64 = base64.b64encode(font_path.read_bytes()).decode()
        parts.append(f"""@font-face {{
    font-family: 'Pretendard';
    src: url(data:font/woff2;base64,{b64}) format('woff2');
    font-weight: {weight};
    font-style: normal;
}}""")

    _cache = "\n".join(parts)
    return _cache
