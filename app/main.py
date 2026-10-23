"""Quick HTTP handlers. Ingestion, hosted generation and speech run as jobs."""
import json
import logging
import re
import uuid
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from fastapi import FastAPI,Request,UploadFile,File,Form,HTTPException,Query
from fastapi.responses import HTMLResponse,JSONResponse,FileResponse,Response
from fastapi.staticfiles import StaticFiles
from app import db,jobs,orchestrate,auth,access
from app.config import settings,ROOT
from app.ingest.arxiv import normalize_id
from app.render.pages import env,viewer,export_html
from app.schema import Level,ReaderProfile
from typing import Literal

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')

@asynccontextmanager
async def lifespan(app):
    db.init_db()
    jobs.recover()
    yield

app=FastAPI(title='iPDF',version='0.1',lifespan=lifespan)
app.include_router(auth.router)
from app.library import router as library_router
app.include_router(library_router)
app.mount('/static',StaticFiles(directory=ROOT/'app/render/static'),name='static')
app.mount('/app-static',StaticFiles(directory=ROOT/'app/ui'),name='app-static')

@app.middleware('http')
async def headers(request,call_next):
    from urllib.parse import urlsplit
    origin=request.headers.get('origin')
    if request.method=='POST' and origin and urlsplit(origin).netloc!=request.headers.get('host'):
        return JSONResponse({'detail':'Submit requests from this app.'},status_code=403)
    if request.method=='POST' and request.url.path.startswith(('/ipdf/create','/audio/','/api/')) and not auth.account(request):
        return JSONResponse({'detail':'Sign in with GitHub to use your private library.'},status_code=401)
    if request.headers.get('content-length','').isdigit() and int(request.headers['content-length'])>26_000_000:
        return JSONResponse({'detail':'Upload a PDF under 25 MB.'},status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    if request.url.path.startswith(('/library','/api/','/ipdf/','/media/','/auth/')):
        response.headers['Cache-Control']='private, no-store'
    return response

@app.get('/',response_class=HTMLResponse)
def home(request:Request):
    chosen=settings.backend()
    return env.get_template('index.html').render(configured=bool(chosen.api_key and chosen.model),user=auth.account(request))

@app.get('/health')
def health():
    backend=settings.backend()
    return {'status':'ok','ipdf_version':'0.1','database':bool(db.query('SELECT 1',one=True)),
            'llm_configured':bool(backend.api_key and backend.model),'tts':settings.tts_provider,
            'github_login_configured':bool((os.getenv('GITHUB_CLIENT_ID') or os.getenv('CLIENT_ID')) and (os.getenv('GITHUB_CLIENT_SECRET') or os.getenv('CLIENT_SECRET'))),
            'ephemeral_storage':os.getenv('HOST_STORAGE_EPHEMERAL','true').lower()=='true'}

@app.get('/spec')
def spec():
    return FileResponse(ROOT/'SPEC.md',media_type='text/plain; charset=utf-8')

@app.post('/ipdf/create',status_code=202)
async def create(request:Request,pdf: Annotated[UploadFile|None,File()]=None,
                 arxiv_id: Annotated[str,Form()]='',level: Annotated[Level,Form()]='beginner',
                 background: Annotated[str,Form(max_length=300)]='',
                 goal: Annotated[Literal['understand','implement','critique'],Form()]='understand',
                 minutes: Annotated[Literal['5','15','30'],Form()]='15',
                 voice: Annotated[Literal['browser','elevenlabs'],Form()]='browser'):
    user=auth.require_account(request)
    mine=db.query("SELECT COUNT(*) AS n FROM jobs WHERE owner_id=? AND kind='create' AND date(created_at)=date('now')",(user['id'],),one=True)['n']
    if mine>=int(os.getenv('MAX_PAPERS_PER_USER_DAY','3')):
        raise HTTPException(429,'Your daily paper allowance is reached. Continue with your saved editions.')
    if bool(pdf)==bool(arxiv_id.strip()):
        raise HTTPException(422,'Choose exactly one source: PDF upload or arXiv ID.')
    daily=db.query("SELECT COUNT(*) AS n FROM jobs WHERE kind='create' AND date(created_at)=date('now')",one=True)['n']
    if daily>=int(os.getenv('MAX_CREATE_JOBS_PER_DAY','20')):
        raise HTTPException(429,'Today’s paper generation allowance is reached. Saved editions and exports remain available.')
    active=db.query("SELECT COUNT(*) AS n FROM jobs WHERE kind='create' AND state IN ('queued','running')",one=True)['n']
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
    profile=ReaderProfile(background=background,goal=goal,minutes=int(minutes),voice=voice)
    label=arxiv_id or (pdf.filename or 'Uploaded paper')
    job=jobs.enqueue('create',orchestrate.create,upload_path,arxiv_id,level,profile.model_dump(),user['id'],owner_id=user['id'],label=label)
    return {'job_id':job,'status_url':f'/ipdf/status/{job}'}

@app.get('/ipdf/status/{job_id}')
def status(job_id: str,request:Request):
    result=jobs.state(job_id)
    user=auth.account(request)
    if not result or not user or result.get('owner_id')!=user['id']:
        raise HTTPException(404,'Job not found.')
    result.pop('args_json',None)
    return result

def document_or_404(document_id,request,write=False):
    access.document(request,document_id,write)
    document=orchestrate.load_document(document_id)
    if not document:
        raise HTTPException(404,'Interactive paper not found.')
    return document

@app.get('/ipdf/{document_id}.json')
def raw_json(document_id: str,request:Request):
    document=document_or_404(document_id,request)
    return Response(document.model_dump_json(indent=2),media_type='application/json',
        headers={'Content-Disposition':f'attachment; filename="{document_id}.ipdf.json"'})

@app.get('/ipdf/{document_id}/export',response_class=HTMLResponse)
def export(document_id: str,request:Request):
    document=document_or_404(document_id,request)
    html=export_html(orchestrate.portable_document(document))
    return HTMLResponse(html,headers={'Content-Disposition':f'attachment; filename="{document_id}.ipdf.html"'})

@app.get('/ipdf/{document_id}',response_class=HTMLResponse)
def view(document_id: str,request:Request):
    return HTMLResponse(viewer(document_or_404(document_id,request),document_id))

@app.post('/audio/{document_id}/{section_id}',status_code=202)
def audio(document_id: str,section_id: str,request:Request,simpler: bool=Query(False)):
    document=document_or_404(document_id,request)
    if not any(n.section_id==section_id for n in document.narration):
        raise HTTPException(404,'No narration is available for this section.')
    user=auth.require_account(request)
    access.document(request,document_id,write=True)
    key=(user['id'],document_id,section_id,simpler,settings.tts_provider,settings.eleven_voice)
    job=jobs.audio_job(key,orchestrate.synthesize,document_id,section_id,simpler,owner_id=user['id'])
    return {'job_id':job,'status_url':f'/ipdf/status/{job}'}

@app.get('/media/papers/{paper_id}.pdf')
def source(paper_id: str,request:Request):
    access.media(request,'paper',paper_id)
    if not re.fullmatch('[a-f0-9]{64}',paper_id):
        raise HTTPException(404,'Source paper not found.')
    path=settings.data_dir/'papers'/f'{paper_id}.pdf'
    if not path.is_file():
        raise HTTPException(404,'Source paper not found.')
    return FileResponse(path,media_type='application/pdf')

@app.get('/media/audio/{audio_hash}.mp3')
def audio_file(audio_hash: str,request:Request):
    access.media(request,'audio',f'/media/audio/{audio_hash}.mp3')
    if not re.fullmatch('[a-f0-9]{64}',audio_hash):
        raise HTTPException(404,'Audio not found.')
    path=settings.data_dir/'audio'/f'{audio_hash}.mp3'
    if not path.is_file():
        raise HTTPException(404,'Audio not found.')
    return FileResponse(path,media_type='audio/mpeg')
