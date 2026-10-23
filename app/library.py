import json
import uuid
from pathlib import Path
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import RedirectResponse,HTMLResponse
from pydantic import BaseModel,Field
from app import auth,access,db,jobs,orchestrate,tutor
from app.render.pages import env
from app.config import ROOT

router=APIRouter()
@router.get('/library',response_class=HTMLResponse)
def library(request:Request):
    user=auth.account(request)
    if not user:return RedirectResponse('/auth/github',status_code=303)
    import os
    return env.get_template('library.html').render(user=user,ephemeral=os.getenv('HOST_STORAGE_EPHEMERAL','true').lower()=='true')

@router.get('/api/library')
def list_library(request:Request):
    user=auth.require_account(request)
    documents=db.query('SELECT i.id,i.json,a.public FROM ipdfs i JOIN document_access a ON a.document_id=i.id WHERE a.account_id=? ORDER BY i.created_at DESC',(user['id'],))
    papers=[]
    for row in documents:
        data=json.loads(row['json'])
        papers.append({'id':row['id'],'title':data['meta']['title'],'level':data['meta']['level'],'public':bool(row['public']),
            'notes':data.get('issues',[]),'narration':len(data.get('narration',[]))})
    queue=db.query('SELECT id,kind,label,state,progress,message,error,result_id,created_at FROM jobs WHERE owner_id=? ORDER BY created_at DESC LIMIT 100',(user['id'],))
    return {'papers':papers,'jobs':queue}

class Sharing(BaseModel):
    public:bool

class Position(BaseModel):
    section_id:str=Field(max_length=200)
    speed:float=Field(ge=.75,le=1.5,allow_inf_nan=False)
    offset:float=Field(default=0,ge=0,le=86400,allow_inf_nan=False)

@router.get('/api/papers/{document_id}/position')
def get_position(document_id:str,request:Request):
    user=auth.require_account(request);access.document(request,document_id,True)
    return db.query('SELECT section_id,speed,offset FROM reading_positions WHERE account_id=? AND document_id=?',(user['id'],document_id),one=True) or {}

@router.post('/api/papers/{document_id}/position')
def save_position(document_id:str,body:Position,request:Request):
    user=auth.require_account(request);access.document(request,document_id,True)
    doc=orchestrate.load_document(document_id)
    if body.section_id not in {s.id for s in doc.sections}:raise HTTPException(422,'Section not found')
    db.execute('INSERT INTO reading_positions VALUES(?,?,?,?,?) ON CONFLICT(account_id,document_id) DO UPDATE SET section_id=excluded.section_id,speed=excluded.speed,offset=excluded.offset',
        (user['id'],document_id,body.section_id,body.speed,body.offset))
    return {'saved':True}

@router.post('/api/papers/{document_id}/sharing')
def sharing(document_id:str,body:Sharing,request:Request):
    access.document(request,document_id,True)
    db.execute('UPDATE document_access SET public=? WHERE document_id=?',(int(body.public),document_id))
    return {'public':body.public,'url':f'/ipdf/{document_id}'}

@router.post('/api/jobs/{job_id}/retry',status_code=202)
def retry(job_id:str,request:Request):
    user=auth.require_account(request)
    row=jobs.state(job_id)
    if not row or row['owner_id']!=user['id']:raise HTTPException(404,'Job not found')
    if row['state']!='error':raise HTTPException(409,'Only failed jobs can be retried')
    tasks={'create':orchestrate.create,'audio':orchestrate.synthesize,'prepare':tutor.prepare,'tutor':tutor.answer}
    if row['kind'] not in tasks or not row['args_json']:raise HTTPException(409,'This older job cannot be resumed')
    # Explicit retries retain the payload and restart the bounded attempt count.
    db.execute("UPDATE jobs SET state='queued',attempts=0,error=NULL WHERE id=?",(job_id,))
    jobs._pool.submit(jobs._execute,job_id,tasks[row['kind']],json.loads(row['args_json']))
    return {'job_id':job_id}

@router.get('/tutor/{document_id}',response_class=HTMLResponse)
def tutor_page(document_id:str,request:Request):
    user=auth.account(request)
    if not user:return RedirectResponse('/auth/github',status_code=303)
    access.document(request,document_id,True)
    document=orchestrate.load_document(document_id)
    return env.get_template('tutor.html').render(user=user,document_id=document_id,document=document)

@router.get('/api/tutor/{document_id}')
def tutor_state(document_id:str,request:Request):
    user=auth.require_account(request);access.document(request,document_id,True)
    row=db.query('SELECT json FROM tutor_maps WHERE account_id=? AND document_id=?',(user['id'],document_id),one=True)
    memory=db.query('SELECT concept,familiar FROM learning WHERE account_id=? AND document_id=?',(user['id'],document_id))
    turns=db.query('SELECT question,answer_json,created_at FROM tutor_turns WHERE account_id=? AND document_id=? ORDER BY created_at DESC LIMIT 20',(user['id'],document_id))
    return {'map':json.loads(row['json']) if row else None,'memory':memory,'turns':[dict(question=r['question'],answer=json.loads(r['answer_json'])) for r in reversed(turns)]}

def allowance(user):
    import os
    active=db.query("SELECT COUNT(*) AS n FROM jobs WHERE owner_id=? AND state IN ('queued','running')",(user['id'],),one=True)['n']
    total=db.query("SELECT COUNT(*) AS n FROM jobs WHERE owner_id=? AND kind IN ('tutor','prepare') AND date(created_at)=date('now')",(user['id'],),one=True)['n']
    global_total=db.query("SELECT COUNT(*) AS n FROM jobs WHERE kind IN ('tutor','prepare') AND date(created_at)=date('now')",one=True)['n']
    if active>=3 or total>=int(os.getenv('MAX_TUTOR_JOBS_PER_USER_DAY','20')) or global_total>=int(os.getenv('MAX_TUTOR_JOBS_PER_DAY','60')):
        raise HTTPException(429,'Tutor allowance reached. Try again after your current work finishes or tomorrow.')

@router.post('/api/tutor/{document_id}/prepare',status_code=202)
def prepare(document_id:str,request:Request):
    user=auth.require_account(request);access.document(request,document_id,True);allowance(user)
    return {'job_id':jobs.enqueue('prepare',tutor.prepare,document_id,user['id'],owner_id=user['id'])}

class Question(BaseModel):
    section_id:str=Field(max_length=200)
    question:str=Field(min_length=3,max_length=1000)

@router.post('/api/tutor/{document_id}/ask',status_code=202)
def ask(document_id:str,body:Question,request:Request):
    user=auth.require_account(request);access.document(request,document_id,True);allowance(user)
    return {'job_id':jobs.enqueue('tutor',tutor.answer,document_id,user['id'],body.section_id,body.question,owner_id=user['id'])}

class Familiarity(BaseModel):
    concept:str=Field(min_length=1,max_length=100)
    familiar:bool

@router.post('/api/tutor/{document_id}/memory')
def memory(document_id:str,body:Familiarity,request:Request):
    user=auth.require_account(request);access.document(request,document_id,True)
    row=db.query('SELECT json FROM tutor_maps WHERE account_id=? AND document_id=?',(user['id'],document_id),one=True)
    if not row or body.concept not in {c['name'] for c in json.loads(row['json'])['concepts']}:
        raise HTTPException(422,'Choose a concept from this paper’s learning path')
    db.execute('INSERT INTO learning(account_id,document_id,concept,familiar) VALUES(?,?,?,?) ON CONFLICT(account_id,document_id,concept) DO UPDATE SET familiar=excluded.familiar,updated_at=CURRENT_TIMESTAMP',
        (user['id'],document_id,body.concept,int(body.familiar)))
    return {'saved':True}

@router.post('/api/tutor/{document_id}/reset')
def reset(document_id:str,request:Request):
    user=auth.require_account(request);access.document(request,document_id,True)
    db.execute('DELETE FROM learning WHERE account_id=? AND document_id=?',(user['id'],document_id))
    db.execute('DELETE FROM tutor_turns WHERE account_id=? AND document_id=?',(user['id'],document_id))
    return {'reset':True}
