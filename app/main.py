"""Quick HTTP handlers. Ingestion, hosted generation and speech run as jobs."""
import json
import logging
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from fastapi import FastAPI,Request,UploadFile,File,Form,HTTPException,Query
from fastapi.responses import HTMLResponse,JSONResponse,FileResponse,Response
from fastapi.staticfiles import StaticFiles
from app import db,jobs,orchestrate
from app.config import settings,ROOT
from app.ingest.arxiv import normalize_id
from app.render.pages import env,viewer,export_html
from app.schema import Level

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')

@asynccontextmanager
async def lifespan(app):
    db.init_db()
    db.execute("UPDATE jobs SET state='error',error='Server restarted. Submit the paper again.',message='Interrupted' WHERE state IN ('queued','running')")
    yield

app=FastAPI(title='iPDF',version='0.1',lifespan=lifespan)
app.mount('/static',StaticFiles(directory=ROOT/'app/render/static'),name='static')

@app.middleware('http')
async def headers(request,call_next):
    from urllib.parse import urlsplit
    origin=request.headers.get('origin')
    if request.method=='POST' and origin and urlsplit(origin).netloc!=request.headers.get('host'):
        return JSONResponse({'detail':'Submit requests from this app.'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    return response

@app.get('/',response_class=HTMLResponse)
def home():
    chosen=settings.backend()
    return env.get_template('index.html').render(configured=bool(chosen.api_key and chosen.model))

@app.get('/health')
def health():
    backend=settings.backend()
    return {'status':'ok','ipdf_version':'0.1','database':bool(db.query('SELECT 1',one=True)),
            'llm_configured':bool(backend.api_key and backend.model),'tts':settings.tts_provider}

@app.get('/spec')
def spec():
    return FileResponse(ROOT/'SPEC.md',media_type='text/plain; charset=utf-8')

@app.post('/ipdf/create',status_code=202)
async def create(pdf: Annotated[UploadFile|None,File()]=None,
                 arxiv_id: Annotated[str,Form()]='',level: Annotated[Level,Form()]='beginner'):
    if bool(pdf)==bool(arxiv_id.strip()):
        raise HTTPException(422,'Choose exactly one source: PDF upload or arXiv ID.')
    active=db.query("SELECT COUNT(*) AS n FROM jobs WHERE state IN ('queued','running')",one=True)['n']
    if active>=8:
        raise HTTPException(429,'The reading room is busy. Wait for an active paper to finish.')
    upload_path=None
    if arxiv_id:
        try:
            arxiv_id=normalize_id(arxiv_id)
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc
    else:
        directory=settings.data_dir/'uploads'
        directory.mkdir(parents=True,exist_ok=True)
        path=directory/(uuid.uuid4().hex+'.pdf')
        total=0
        try:
            with path.open('wb') as output:
                while chunk:=await pdf.read(1_000_000):
                    if total==0 and not chunk.startswith(b'%PDF'):
                        raise HTTPException(422,'This file does not have a PDF header.')
                    total+=len(chunk)
                    if total>25_000_000:
                        raise HTTPException(413,'Upload a PDF under 25 MB.')
                    output.write(chunk)
            if not total:
                raise HTTPException(422,'The PDF is empty.')
            upload_path=str(path)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            await pdf.close()
    job=jobs.enqueue('create',orchestrate.create,upload_path,arxiv_id,level)
    return {'job_id':job,'status_url':f'/ipdf/status/{job}'}

@app.get('/ipdf/status/{job_id}')
def status(job_id: str):
    result=jobs.state(job_id)
    if not result:
        raise HTTPException(404,'Job not found.')
    return result

def document_or_404(document_id):
    document=orchestrate.load_document(document_id)
    if not document:
        raise HTTPException(404,'Interactive paper not found.')
    return document

@app.get('/ipdf/{document_id}.json')
def raw_json(document_id: str):
    document=document_or_404(document_id)
    return Response(document.model_dump_json(indent=2),media_type='application/json',
        headers={'Content-Disposition':f'attachment; filename="{document_id}.ipdf.json"'})

@app.get('/ipdf/{document_id}/export',response_class=HTMLResponse)
def export(document_id: str):
    document=document_or_404(document_id)
    html=export_html(orchestrate.portable_document(document))
    return HTMLResponse(html,headers={'Content-Disposition':f'attachment; filename="{document_id}.ipdf.html"'})

@app.get('/ipdf/{document_id}',response_class=HTMLResponse)
def view(document_id: str):
    return HTMLResponse(viewer(document_or_404(document_id),document_id))

@app.post('/audio/{document_id}/{section_id}',status_code=202)
def audio(document_id: str,section_id: str,simpler: bool=Query(False)):
    document=document_or_404(document_id)
    if not any(n.section_id==section_id for n in document.narration):
        raise HTTPException(404,'No narration is available for this section.')
    key=(document_id,section_id,simpler,settings.tts_provider,settings.eleven_voice)
    job=jobs.audio_job(key,orchestrate.synthesize,document_id,section_id,simpler)
    return {'job_id':job,'status_url':f'/ipdf/status/{job}'}

@app.get('/media/papers/{paper_id}.pdf')
def source(paper_id: str):
    if not re.fullmatch('[a-f0-9]{64}',paper_id):
        raise HTTPException(404,'Source paper not found.')
    path=settings.data_dir/'papers'/f'{paper_id}.pdf'
    if not path.is_file():
        raise HTTPException(404,'Source paper not found.')
    return FileResponse(path,media_type='application/pdf')

@app.get('/media/audio/{audio_hash}.mp3')
def audio_file(audio_hash: str):
    if not re.fullmatch('[a-f0-9]{64}',audio_hash):
        raise HTTPException(404,'Audio not found.')
    path=settings.data_dir/'audio'/f'{audio_hash}.mp3'
    if not path.is_file():
        raise HTTPException(404,'Audio not found.')
    return FileResponse(path,media_type='audio/mpeg')
