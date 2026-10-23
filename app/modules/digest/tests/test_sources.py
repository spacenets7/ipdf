from app.modules.digest.sources.arxiv import parse_feed, topic_query
from app.extract import chunks, select_text, pdf_text
import pymupdf


def test_arxiv_atom():
    atom = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2601.12345v1</id>
      <title>A research paper</title><summary>Real source abstract.</summary><published>2026-01-01T00:00:00Z</published>
      <author><name>A Researcher</name></author><category term="cs.AI"/></entry></feed>'''
    item = parse_feed(atom)[0]
    assert item.tags == ['cs.AI']
    assert item.url.startswith('https://')
    assert 'cat:cs.LG' in topic_query(['machine learning'])
    assert '" AND' not in topic_query(['x" AND cat:all'])


def test_pdf_and_section_selection():
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((50,50),'Abstract. This paper investigates local research tools. ' * 4)
    assert 'investigates' in pdf_text(document.tobytes())
    text = 'Abstract\n' + 'a'*26000 + '\n1 Introduction\n'+'b'*26000+'\n5 Conclusion\nimportant result'
    selected = select_text(text)
    assert len(selected) <= 24000
    assert 'important result' in selected
    parts = list(chunks('abcdefghij',size=6,overlap=2))
    assert parts == ['abcdef','efghij']
