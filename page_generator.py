import shutil
from pathlib import Path


def generate_gallery(output_dir, docs_dir):
    output_path = Path(output_dir)
    docs_path = Path(docs_dir)
    docs_path.mkdir(parents=True, exist_ok=True)

    date_dirs = sorted(
        [d for d in output_path.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )

    sections_html = ""
    for date_dir in date_dirs:
        cards = sorted(date_dir.glob("card-*.png"))
        if not cards:
            continue

        # 이미지를 docs/cards/ 안에 복사
        cards_dest = docs_path / "cards" / date_dir.name
        cards_dest.mkdir(parents=True, exist_ok=True)
        for card in cards:
            shutil.copy2(card, cards_dest / card.name)

        cards_html = ""
        for card in cards:
            rel_path = f"cards/{date_dir.name}/{card.name}"
            cards_html += f"""
            <a href="{rel_path}" download="{card.name}" class="card-link" data-filename="{card.name}">
                <img src="{rel_path}" alt="{card.name}" class="card-img">
            </a>"""

        sections_html += f"""
        <section class="date-section">
            <h2>{date_dir.name}</h2>
            <div class="card-grid">{cards_html}
            </div>
        </section>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Card News Gallery</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: #0a0a0a; color: #fff;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            padding: 40px 20px;
            max-width: 1200px; margin: 0 auto;
        }}
        h1 {{
            font-size: 48px; font-weight: 900;
            letter-spacing: -2px; margin-bottom: 8px;
        }}
        .subtitle {{
            color: #666; font-size: 18px; margin-bottom: 60px;
        }}
        .date-section {{
            margin-bottom: 60px;
        }}
        h2 {{
            font-size: 24px; font-weight: 600;
            color: #888; margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid #222;
        }}
        .card-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
        }}
        .card-link {{
            display: block;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #2a2a2a;
            transition: border-color 0.2s;
        }}
        .card-link:hover {{
            border-color: #555;
        }}
        .card-img {{
            width: 100%; height: auto; display: block;
        }}
        @media (max-width: 768px) {{
            .card-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            h1 {{ font-size: 32px; }}
        }}
    </style>
</head>
<body>
    <h1>AI Card News</h1>
    <p class="subtitle">매일 자동 생성되는 AI 뉴스 카드</p>
    {sections_html}
    <script>
    document.querySelectorAll('.card-link').forEach(link => {{
        link.addEventListener('click', async (e) => {{
            e.preventDefault();
            const url = link.href;
            const filename = link.dataset.filename;
            try {{
                const res = await fetch(url);
                const blob = await res.blob();
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = filename;
                a.click();
                URL.revokeObjectURL(a.href);
            }} catch {{
                window.open(url);
            }}
        }});
    }});
    </script>
</body>
</html>"""

    (docs_path / "index.html").write_text(html, encoding="utf-8")
