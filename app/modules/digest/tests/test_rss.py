from datetime import datetime,timezone
from unittest.mock import patch
from app.modules.digest.sources.rss import RSSSource


def test_same_item_shape_with_article_extraction():
    feed=b'''<rss version="2.0"><channel><title>Research</title><item><title>New finding</title>
    <link>https://example.com/news/1</link><pubDate>Fri, 23 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>'''
    article='<html><body><article><h1>New finding</h1>'+('<p>Researchers investigate how local language models help readers understand research papers.</p>'*20)+'</article></body></html>'
    with patch('app.modules.digest.sources.rss.public_url',side_effect=lambda url:url), \
         patch('app.modules.digest.sources.rss.download',side_effect=[feed,article.encode()]):
        result=RSSSource('https://example.com/rss').fetch([],datetime(2026,10,22,tzinfo=timezone.utc))
    assert len(result)==1
    assert result[0].source=='rss'
    assert len(result[0].raw_text)>100
