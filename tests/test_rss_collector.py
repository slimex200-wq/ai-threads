import sys
sys.path.insert(0, '.')
from rss_collector import collect_news

def test_collect_news_returns_list():
    articles = collect_news(max_count=2)
    assert isinstance(articles, list)
    assert len(articles) <= 2

def test_article_has_required_fields():
    articles = collect_news(max_count=1)
    if articles:
        article = articles[0]
        assert "title" in article
        assert "summary" in article
        assert "source" in article
        assert "link" in article
