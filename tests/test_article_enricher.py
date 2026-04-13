from article_enricher import extract_article_text


def test_extract_article_text_collects_paragraphs():
    html = """
    <html>
      <body>
        <article>
          <p>Liquid AI released a 450M VLM for Galaxy S25 Ultra.</p>
          <p>The model runs on-device and handles image understanding tasks.</p>
          <p>It focuses on low latency and privacy-sensitive workloads.</p>
        </article>
      </body>
    </html>
    """

    text = extract_article_text(html)

    assert "Liquid AI released a 450M VLM" in text
    assert "privacy-sensitive workloads" in text
