"""The only layer coordinating ingestion, generation, persistence and jobs."""
import hashlib
import json
import uuid
import base64
import re
from pathlib import Path
from app import db,jobs
from app.config import settings
from app.extract import extract_document
from app.ingest.arxiv import fetch_pdf
from app.generate.pipeline import build
from app.generate.common import VERSIONS,reader_context
from app.llm import run_id
from app.schema import IPDF


def cache_key(paper_id,level,reader=None):
    fast,deep=settings.backend(),settings.backend('DEEP')
    return hashlib.sha256(json.dumps(['ingest/0.1.2',paper_id,level,fast.model,fast.base_url,
        deep.model,deep.base_url,bool(fast.api_key and fast.model),VERSIONS,reader or {}],sort_keys=True).encode()).hexdigest()


def load_document(document_id):
    row=db.query('SELECT json FROM ipdfs WHERE id=?',(document_id,),one=True)
    if not row:
        return None
    document=IPDF.model_validate_json(row['json'])
    document.meta.tts_provider=document.meta.reader.voice
    return document


def portable_document(document):
    """Assemble portable content before passing JSON to the rendering layer."""
    document=document.model_copy(deep=True)
    pdf=settings.data_dir/'papers'/f'{document.meta.paper_id}.pdf'
    if pdf.is_file():
        document.assets.original_pdf='data:application/pdf;base64,'+base64.b64encode(pdf.read_bytes()).decode()
    for segment in document.narration:
        for field in ('audio_url','simpler_audio_url'):
            url=getattr(segment,field)
            if url and re.fullmatch(r'/media/audio/[a-f0-9]{64}\.mp3',url):
                path=settings.data_dir/'audio'/Path(url).name
                setattr(segment,field,'data:audio/mpeg;base64,'+base64.b64encode(path.read_bytes()).decode() if path.is_file() else None)
            elif url and url.startswith('/'):
                setattr(segment,field,None)
    return IPDF.model_validate(document.model_dump())


def create(job,upload_path,arxiv_id,level,reader=None,owner_id=None):
    token=run_id.set(job)
    profile_token=reader_context.set(reader or {})
    try:
        jobs.update(job,progress=5,message='Opening the source paper')
        metadata={}
        if arxiv_id:
            jobs.update(job,progress=8,message='Downloading from arXiv')
            content,metadata=fetch_pdf(arxiv_id)
        else:
            content=Path(upload_path).read_bytes()
        jobs.update(job,progress=15,message='Extracting source text, tables and figures')
        paper=extract_document(content,metadata)
        key=hashlib.sha256((cache_key(paper.paper_id,level,reader)+str(owner_id)).encode()).hexdigest()
        cached=db.query('SELECT id,json FROM ipdfs WHERE cache_key=?',(key,),one=True)
        needs_retry=bool(cached and settings.backend().api_key and settings.backend().model and
            any(issue['plugin']=='configuration' for issue in json.loads(cached['json']).get('issues',[])))
        if cached and not needs_retry:
            if owner_id:
                db.execute('INSERT INTO document_access(document_id,account_id) VALUES(?,?) ON CONFLICT(document_id) DO NOTHING',(cached['id'],owner_id))
                jobs.enqueue('prepare',__import__('app.tutor',fromlist=['prepare']).prepare,cached['id'],owner_id,owner_id=owner_id)
            jobs.update(job,'ready',100,'Loaded the saved interactive edition',result_id=cached['id'])
            return
        directory=settings.data_dir/'papers'
        directory.mkdir(parents=True,exist_ok=True)
        path=directory/f'{paper.paper_id}.pdf'
        path.write_bytes(content)
        if not paper.source_url:
            paper.source_url=f'/media/papers/{paper.paper_id}.pdf'
        db.execute('''INSERT INTO papers(id,title,source_url,pdf_path,ingest_json) VALUES(?,?,?,?,?)
            ON CONFLICT(id) DO NOTHING''',(paper.paper_id,paper.title,paper.source_url,str(path),paper.model_dump_json()))
        document=build(paper,level,lambda p,m:jobs.update(job,progress=p,message=m))
        jobs.update(job,progress=95,message='Validating the iPDF edition')
        document=IPDF.model_validate(document.model_dump())
        document_id=uuid.uuid4().hex
        db.execute('''INSERT INTO ipdfs(id,paper_id,level,model,cache_key,json) VALUES(?,?,?,?,?,?)
            ON CONFLICT(cache_key) DO UPDATE SET json=excluded.json,model=excluded.model''',
            (document_id,paper.paper_id,level,document.provenance.model,key,document.model_dump_json()))
        actual=db.query('SELECT id FROM ipdfs WHERE cache_key=?',(key,),one=True)['id']
        if owner_id:
            db.execute('INSERT INTO document_access(document_id,account_id) VALUES(?,?) ON CONFLICT(document_id) DO NOTHING',(actual,owner_id))
            # Queue the prerequisite map while the reader is away. No browser polling required.
            jobs.enqueue('prepare',__import__('app.tutor',fromlist=['prepare']).prepare,actual,owner_id,owner_id=owner_id)
            if document.meta.reader.voice=='elevenlabs':
                for segment in document.narration:
                    jobs.audio_job((owner_id,actual,segment.section_id,False),synthesize,actual,segment.section_id,False,owner_id=owner_id)
        jobs.update(job,'ready',100,'Your interactive paper is ready',result_id=actual)
    finally:
        reader_context.reset(profile_token)
        run_id.reset(token)
        if upload_path and jobs.state(job)['state']=='ready':
            Path(upload_path).unlink(missing_ok=True)


_document_locks={}
import threading
_locks_guard=threading.Lock()


def synthesize(job,document_id,section_id,simpler):
    from app.audio import create_audio
    document=load_document(document_id)
    if not document:
        raise ValueError('Interactive paper was not found.')
    narration=next((n for n in document.narration if n.section_id==section_id),None)
    if not narration:
        raise ValueError('This section does not have narration.')
    jobs.update(job,progress=20,message='Preparing section audio')
    result=create_audio(narration.simpler_script if simpler else narration.script,provider=document.meta.reader.voice)
    if result.get('audio_url'):
        with _locks_guard:
            lock=_document_locks.setdefault(document_id,threading.Lock())
        with lock:
            latest=load_document(document_id)
            segment=next(n for n in latest.narration if n.section_id==section_id)
            if simpler:
                segment.simpler_audio_url=result['audio_url']
            else:
                segment.audio_url=result['audio_url']
            db.execute('UPDATE ipdfs SET json=? WHERE id=?',(latest.model_dump_json(),document_id))
    jobs.update(job,'ready',100,'Audio is ready',result_id=document_id,result=result)
