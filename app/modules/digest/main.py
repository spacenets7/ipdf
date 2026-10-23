import json
import logging
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, Response, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app import db
from app.config import settings, ROOT
from app.modules.digest.digest import build_digest, latest_digest, today, profile_key
from app.modules.digest.feedback import apply_feedback
from app.modules.digest.levels import effective_level

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
log = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2,thread_name_prefix='digest')
_jobs = {}
_jobs_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    yield


app = FastAPI(title='LazyDigest',lifespan=lifespan)
app.mount('/static',StaticFiles(directory=ROOT/'app/static'),name='static')
templates = Jinja2Templates(directory=ROOT/'app/templates')


@app.middleware('http')
async def local_origin(request,call_next):
    if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('origin'):
        from urllib.parse import urlsplit
        if urlsplit(request.headers['origin']).netloc != request.headers.get('host'):
            return JSONResponse({'detail':'Requests must come from this app.'},status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Cache-Control']='no-store' if not request.url.path.startswith('/static') else 'public, max-age=3600'
    return response


def reader(request):
    user = db.get_user(request.cookies.get('user_id'))
    if not user:
        raise HTTPException(401,'Choose your reading preferences first.')
    return user


def context(request,user=None,**extra):
    return dict(request=request,user=user,level=effective_level(user) if user else None,
                fast_model=settings.backend('FAST').model,deep_model=settings.backend('DEEP').model,
                deep_local=settings.backend('DEEP').name=='FAST',**extra)


def _generate(user):
    try:
        digest=build_digest(user,refresh=True)
        with _jobs_lock:
            _jobs[user['id']]={'state':'ready','digest_id':digest['id']}
    except Exception:
        log.exception('Digest generation failed')
        with _jobs_lock:
            _jobs[user['id']]={'state':'error','message':'Your papers are saved, but generation could not finish. Check Ollama and the selected model, then try again.'}


def schedule(user):
    with _jobs_lock:
        if _jobs.get(user['id'],{}).get('state') == 'building':
            return
        _jobs[user['id']]={'state':'building'}
        _executor.submit(_generate,user)


@app.get('/',response_class=HTMLResponse)
def index(request: Request):
    user=db.get_user(request.cookies.get('user_id'))
    return templates.TemplateResponse(request=request,name='index.html',context=context(request,user))


@app.post('/start')
def start(request: Request,name: str=Form(...,min_length=1,max_length=80),
          level: Literal['beginner','intermediate','expert']=Form('intermediate'),
          topics: list[str]=Form(default=[]),custom_topics: str=Form(default='',max_length=600)):
    topics=list(dict.fromkeys(t.strip()[:80] for t in topics+custom_topics.split(',') if t.strip()))[:12]
    if not topics:
        raise HTTPException(422,'Choose at least one topic.')
    if not name.strip():
        raise HTTPException(422,'Enter your name.')
    existing=db.get_user(request.cookies.get('user_id'))
    user_id=existing['id'] if existing else uuid.uuid4().hex
    weights=existing['topic_weights'] if existing else {}
    offset=existing['level_offset'] if existing and existing['level']==level else 0
    db.execute('''INSERT INTO users(id,name,level,topics_json,topic_weights_json,level_offset) VALUES(?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET name=excluded.name,level=excluded.level,topics_json=excluded.topics_json,
        topic_weights_json=excluded.topic_weights_json,level_offset=excluded.level_offset''',
        (user_id,name.strip(),level,json.dumps(topics),json.dumps(weights),offset))
    response=RedirectResponse('/digest',status_code=303)
    response.set_cookie('user_id',user_id,httponly=True,samesite='lax',max_age=365*86400,
                        secure=request.url.scheme=='https')
    return response


@app.get('/digest',response_class=HTMLResponse)
def digest_page(request: Request):
    user=db.get_user(request.cookies.get('user_id'))
    if not user:
        return RedirectResponse('/',status_code=303)
    digest=latest_digest(user['id'])
    current=bool(digest and digest['date']==today() and digest['profile_key']==profile_key(user))
    job=_jobs.get(user['id'],{})
    if not current and not job:
        schedule(user)
        job={'state':'building'}
    elif not current and job.get('state')=='ready':
        schedule(user)
        job={'state':'building'}
    building=job.get('state')=='building'
    return templates.TemplateResponse(request=request,name='digest.html',context=context(request,user,
        digest=digest,building=building,error=job.get('message') if job.get('state')=='error' else None),
        status_code=202 if building and not digest else 200)


@app.get('/digest/status')
def digest_status(request: Request):
    user=reader(request)
    return _jobs.get(user['id'],{'state':'ready' if latest_digest(user['id']) else 'idle'})


@app.post('/digest/refresh')
def refresh(request: Request):
    user=reader(request)
    schedule(user)
    return {'state':'building'}


@app.get('/digest.md')
def download(request: Request):
    digest=latest_digest(reader(request)['id'])
    if not digest:
        raise HTTPException(404,'Build a digest first.')
    return Response(digest['markdown'],media_type='text/markdown; charset=utf-8',
                    headers={'Content-Disposition':'attachment; filename="digest.md"'})


class FeedbackBody(BaseModel):
    item_id: int
    signal: Literal['up','down','too_hard','too_easy']


def owned_rows(user_id):
    return [row for digest in db.query('SELECT payload_json FROM digests WHERE user_id=? ORDER BY id DESC',(user_id,))
            for row in json.loads(digest['payload_json'])]


@app.post('/feedback')
def feedback(request: Request,body: FeedbackBody):
    user=reader(request)
    if not any(row['item']['id']==body.item_id for row in owned_rows(user['id'])):
        raise HTTPException(404,'Paper is not in your digests.')
    return apply_feedback(user['id'],body.item_id,body.signal)


def audio_response(row, *, user_id, digest_id=None):
    from app.audio import create_audio, AudioError
    try:
        return create_audio(row,user_id=user_id,item_id=row.get('item',{}).get('id') if not digest_id else None,
                            digest_id=digest_id)
    except AudioError as exc:
        raise HTTPException(503,str(exc)) from exc


@app.post('/audio/digest')
def digest_audio(request: Request):
    user=reader(request)
    digest=latest_digest(user['id'])
    if not digest or not digest['rows']:
        raise HTTPException(404,'Build a digest with papers first.')
    return audio_response({'title':'Your LazyDigest','level':digest['rows'][0]['level'],
                           'digest_rows':digest['rows']},user_id=user['id'],digest_id=digest['id'])


@app.post('/audio/{item_id}')
def item_audio(request: Request,item_id: int,
               level: Literal['beginner','intermediate','expert']|None=Query(None)):
    user=reader(request)
    row=next((row for row in owned_rows(user['id']) if row['item']['id']==item_id and (level is None or row['level']==level)),None)
    if not row:
        raise HTTPException(404,'Paper at that level is not in your digests.')
    return audio_response(row,user_id=user['id'])


@app.get('/audio/file/{file_hash}.mp3')
def audio_file(request: Request,file_hash: str):
    import re
    user=reader(request)
    if not re.fullmatch('[a-f0-9]{64}',file_hash):
        raise HTTPException(404,'Audio not found.')
    audio=db.query('SELECT * FROM audio WHERE text_hash=?',(file_hash,),one=True)
    if not audio:
        raise HTTPException(404,'Audio not found.')
    grant=db.query('SELECT 1 FROM audio_access WHERE user_id=? AND text_hash=?',(user['id'],file_hash),one=True)
    if grant:
        allowed=True
    elif audio['digest_id']:
        allowed=db.query('SELECT id FROM digests WHERE id=? AND user_id=?',(audio['digest_id'],user['id']),one=True)
    else:
        allowed=any(r['item']['id']==audio['item_id'] for r in owned_rows(user['id']))
    path=settings.data_dir/'audio'/f'{file_hash}.mp3'
    if not allowed or not path.is_file():
        raise HTTPException(404,'Audio not found.')
    return FileResponse(path,media_type='audio/mpeg')


@app.get('/health')
def health():
    model_ready=False
    try:
        backend=settings.backend('FAST')
        with httpx.Client(timeout=2) as client:
            response=client.get(backend.base_url.rstrip('/')+'/models',headers={'Authorization':'Bearer '+backend.api_key})
            response.raise_for_status()
        model_ready=any(m['id']==backend.model for m in response.json().get('data',[]))
    except Exception:
        pass
    return {'status':'ok','database':bool(db.query('SELECT 1',one=True)),
            'local_model_ready':model_ready,'fast_model':settings.backend('FAST').model,
            'deep_backend':settings.backend('DEEP').name,'offline':settings.offline,
            'local_voice_ready':settings.piper_model.is_file(),'ffmpeg_ready':bool(shutil.which('ffmpeg'))}
