import base64
import hashlib
import logging
import re
import threading
import pymupdf
from pydantic import BaseModel,Field
from app.config import settings
from app.schema import Section,Table,Figure,parse_number

log=logging.getLogger(__name__)
_pdf_lock=threading.Lock()


class Ingested(BaseModel):
    paper_id: str
    title: str
    authors: list[str]
    source_url: str
    pages: int
    sections: list[Section]
    tables: list[Table]=Field(default_factory=list)
    figures: list[Figure]=Field(default_factory=list)
    warnings: list[str]=Field(default_factory=list)


def _captions(page,kind='Table'):
    captions=[]
    for block in page.get_text('blocks'):
        text=str(block[4])
        match=re.search(r'(?m)^\s*'+kind+r'\s*(\d+)\s*[:.]',text,re.I)
        if match:
            captions.append((f'{kind} {match.group(1)}',pymupdf.Rect(block[:4]),text.strip()))
    return captions


def _usable_table(cells):
    nonempty=[c for row in cells for c in row if c]
    numeric=sum(parse_number(c) is not None for c in nonempty)
    width=max((len(r) for r in cells),default=0)
    # Text alignment can split a word/decimal into phantom columns or mistake
    # nearby prose for a table. Prefer omission when the grid is ambiguous.
    fragmented=any(re.fullmatch(r'[-+]?\d+',str(a or '')) and re.fullmatch(r'\.\d+',str(b or ''))
        for row in cells for a,b in zip(row,row[1:]))
    header_density=sum(bool(c) for c in cells[0])/max(1,width) if cells else 0
    return len(cells)>=3 and width>=2 and numeric>=2 and numeric/max(1,len(nonempty))>=.2 \
        and not fragmented and (width<=6 or header_density>=.7)


def extract_tables(page,page_number):
    captions=_captions(page)
    candidates=[]
    try:
        candidates=list(page.find_tables().tables)
        # Borderless tables are common in research. Restrict text alignment
        # extraction to regions adjacent to an actual printed table caption.
        if not candidates:
            for _,box,_ in captions:
                for top,bottom in ((max(0,box.y0-230),box.y0),(box.y1,min(page.rect.height,box.y1+230))):
                    clip=pymupdf.Rect(max(0,box.x0-8),top,min(page.rect.width,box.x1+8),bottom)
                    if clip.height>20:
                        candidates.extend(page.find_tables(clip=clip,strategy='text',min_words_vertical=3).tables)
    except Exception as exc:
        log.warning('Table extraction p.%d failed (%s)',page_number,type(exc).__name__)
    tables=[]
    seen=set()
    for candidate in candidates:
        try:
            cells=[[str(c).strip() if c is not None else None for c in row] for row in candidate.extract()]
            cells=[row for row in cells if any(c for c in row)]
            expanded=[]
            for row in cells:
                counts=[len(c.splitlines()) for c in row if c]
                if counts and max(counts)>1 and len(set(counts))==1:
                    expanded.extend([[c.splitlines()[i] if c else None for c in row] for i in range(counts[0])])
                else:
                    expanded.append(row)
            cells=expanded
            if not _usable_table(cells):
                continue
            fingerprint=str(cells)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            bounds=pymupdf.Rect(candidate.bbox)
            nearby=sorted(captions,key=lambda cap:min(abs(cap[1].y0-bounds.y1),abs(cap[1].y1-bounds.y0)))
            label=nearby[0][0] if nearby and min(abs(nearby[0][1].y0-bounds.y1),abs(nearby[0][1].y1-bounds.y0))<250 else f'Unnumbered table {len(tables)+1}'
            # Avoid counting two candidate crops as the same numbered table.
            if any(t.label==label for t in tables) and label.startswith('Table'):
                continue
            tables.append(Table(id=f'p{page_number}-t{len(tables)+1}',label=label,page=page_number,cells=cells))
        except Exception as exc:
            log.warning('Dropping invalid table p.%d (%s)',page_number,type(exc).__name__)
    return tables


def extract_figures(document,page,page_number):
    figures=[]
    captions=_captions(page,'Figure')
    for image in page.get_images(full=True)[:12]:
        try:
            xref=image[0]
            if image[2]<150 or image[3]<100:
                continue
            pix=pymupdf.Pixmap(document,xref)
            if pix.colorspace and pix.colorspace.n>3:
                pix=pymupdf.Pixmap(pymupdf.csRGB,pix)
            if pix.width>1200:
                pix=pymupdf.Pixmap(pix,0) if pix.alpha else pix
                pix.shrink(1)
            png=pix.tobytes('png')
            if len(png)>1_000_000:
                continue
            label=captions[len(figures)][2] if len(captions)>len(figures) else f'Extracted image on page {page_number}'
            figures.append(Figure(id=f'p{page_number}-f{len(figures)+1}',page=page_number,
                caption=label[:600],data_url='data:image/png;base64,'+base64.b64encode(png).decode()))
        except Exception:
            log.warning('Skipping unusable figure on p.%d',page_number)
    return figures


def ingest_pdf(content,metadata=None):
    # MuPDF work is serialized; network/plugin work can still run concurrently.
    with _pdf_lock:
        return _ingest_pdf(content,metadata)


def _ingest_pdf(content,metadata=None):
    metadata=metadata or {}
    if not content.startswith(b'%PDF') or len(content)>25_000_000:
        raise ValueError('Upload a PDF under 25 MB.')
    paper_id=hashlib.sha256(content).hexdigest()
    try:
        document=pymupdf.open(stream=content,filetype='pdf')
    except Exception as exc:
        raise ValueError('This PDF could not be opened.') from exc
    with document:
        if document.needs_pass:
            raise ValueError('Password-protected PDFs are not supported.')
        if len(document)>settings.max_pages:
            raise ValueError(f'This PDF has {len(document)} pages. The limit is {settings.max_pages}.')
        sections,tables,figures=[],[],[]
        for index,page in enumerate(document):
            text=page.get_text(sort=True).strip()
            if not text:
                continue
            lines=[line.strip() for line in text.splitlines() if line.strip()]
            heading=next((line for line in lines[:20] if re.match(r'^\d+(?:\.\d+)*\s+[A-Z]',line) and len(line)<100),None)
            # Numbered affiliations on the title page are not section headings.
            title='Opening page' if index==0 else (heading or f'Page {index+1}')
            sections.append(Section(id=f'p{index+1}',title=title,page=index+1,text=text))
            tables.extend(extract_tables(page,index+1))
            figures.extend(extract_figures(document,page,index+1))
        if not sections or sum(len(s.text) for s in sections)<100:
            raise ValueError('No usable text layer found. Scanned papers require OCR before upload.')
        title=metadata.get('title') or document.metadata.get('title')
        if not title or len(title)<5 or 'untitled' in title.lower() or title.lower().startswith('arxiv:'):
            spans=[span for block in document[0].get_text('dict')['blocks'] if 'lines' in block
                   for line in block['lines'] for span in line['spans'] if len(span['text'].strip())>5
                   and not span['text'].strip().lower().startswith('arxiv:') and abs(line['dir'][1])<.2]
            if spans:
                size=max(span['size'] for span in spans)
                title=' '.join(span['text'].strip() for span in spans if abs(span['size']-size)<.2)
            else:
                title='Untitled paper'
        authors=metadata.get('authors') or ([document.metadata['author']] if document.metadata.get('author') else [])
        return Ingested(paper_id=paper_id,title=title[:800],authors=authors,source_url=metadata.get('source_url',''),
            pages=len(document),sections=sections,tables=tables,figures=figures,
            warnings=[] if tables else ['No reliable tables were extracted. Charts will be omitted.'])
