"""Retain the full paper; select abstract, introduction and conclusion for FAST."""
import logging
import re
import httpx
import pymupdf
from app.config import settings

log = logging.getLogger(__name__)
TEXT_CAP = 24_000


def extract_document(content,metadata=None):
    """iPDF entry point; retain the existing PDF utilities for the digest module."""
    from app.ingest.pdf import ingest_pdf
    return ingest_pdf(content,metadata)


def chunks(text, size=TEXT_CAP, overlap=600):
    if size <= overlap or overlap < 0:
        raise ValueError('Chunk size must exceed overlap')
    for start in range(0,len(text),size-overlap):
        yield text[start:start+size]
        if start+size >= len(text):
            break


def select_text(text, cap=TEXT_CAP):
    if len(text) <= cap:
        return text
    sections = [text[:cap//3]]
    for pattern in (r'(?im)^\s*(?:\d+[. ]+)?introduction\b', r'(?im)^\s*(?:\d+[. ]+)?conclusions?\b'):
        match = re.search(pattern,text)
        if match:
            sections.append(text[match.start():match.start()+cap//3])
    if len(sections) < 3:
        sections.append(text[-cap//3:])
    return '\n\n[Selected source sections]\n\n'.join(sections)[:cap]


def pdf_text(content):
    with pymupdf.open(stream=content,filetype='pdf') as document:
        # Bound malicious/huge PDF work while retaining ordinary full papers.
        text = '\n'.join(document[i].get_text(sort=True) for i in range(min(len(document),100)))
    text = re.sub(r'[ \t]+',' ',text)
    if len(text.strip()) < 100:
        raise ValueError('PDF has no usable text layer')
    return text[:400_000]


def enrich(item, *, full=False):
    if settings.offline or not item.get('pdf_url'):
        return item['raw_text']
    if not full and len(item['raw_text']) >= 700:
        return item['raw_text']
    if len(item['raw_text']) > 5000:
        return item['raw_text']
    url = item['pdf_url']
    if not re.fullmatch(r'https://arxiv\.org/pdf/[\w./-]+',url):
        return item['raw_text']
    try:
        with httpx.Client(timeout=40,follow_redirects=True) as client:
            with client.stream('GET',url) as response:
                response.raise_for_status()
                data = bytearray()
                for part in response.iter_bytes():
                    data.extend(part)
                    if len(data) > 25_000_000:
                        raise ValueError('PDF exceeds 25 MB')
        text = item['raw_text']+'\n\n'+pdf_text(bytes(data))
        from app import db
        db.execute('UPDATE items SET raw_text=? WHERE id=?',(text,item['id']))
        return text
    except Exception as exc:
        log.warning('PDF extraction failed for %s (%s); using abstract',item['external_id'],type(exc).__name__)
        return item['raw_text']
