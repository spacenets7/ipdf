import pymupdf
import pytest
from app.extract import extract_document
from app.ingest.arxiv import normalize_id


def make_pdf():
    doc=pymupdf.open()
    for n in range(2):
        page=doc.new_page()
        page.insert_text((40,45),f'{n+1} Introduction',fontsize=18)
        page.insert_text((40,85),'Research on interactive papers provides a source text layer. '*5)
    return doc.tobytes()


def test_page_tagged_ingestion_and_stable_identity():
    raw=make_pdf()
    result=extract_document(raw,{'title':'Test paper'})
    assert result.pages==2
    assert [s.page for s in result.sections]==[1,2]
    assert result.paper_id==extract_document(raw).paper_id
    assert result.sections[0].title=='1 Introduction'


def test_bad_pdf_and_id():
    with pytest.raises(ValueError):
        extract_document(b'not a pdf')
    assert normalize_id('https://arxiv.org/abs/1706.03762')=='1706.03762'
    with pytest.raises(ValueError):
        normalize_id('http://127.0.0.1/private')
