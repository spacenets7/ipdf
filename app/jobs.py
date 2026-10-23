"""Persistent job state; request handlers enqueue work and return immediately."""
import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from app import db

log=logging.getLogger(__name__)
_pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='ipdf-job')
_lock=threading.Lock()
_audio_jobs={}


def update(job,state='running',progress=0,message='',result_id=None,result=None,error=None):
    db.execute('''UPDATE jobs SET state=?,progress=?,message=?,result_id=COALESCE(?,result_id),
        result_json=COALESCE(?,result_json),error=?,updated_at=CURRENT_TIMESTAMP WHERE id=?''',
        (state,progress,message,result_id,json.dumps(result) if result is not None else None,error,job))


def enqueue(kind,task,*args):
    job=uuid.uuid4().hex
    db.execute('INSERT INTO jobs(id,kind,state,message) VALUES(?,?,?,?)',(job,kind,'queued','Waiting to begin'))
    _pool.submit(_execute,job,task,args)
    return job


def _execute(job,task,args):
    try:
        update(job,progress=1,message='Starting')
        task(job,*args)
    except Exception as exc:
        log.exception('Job %s failed (%s)',job,type(exc).__name__)
        # Provider exception strings may contain endpoint or token details.
        message=str(exc) if isinstance(exc,ValueError) else 'Processing failed. Check the source file and hosted provider configuration, then try again.'
        update(job,state='error',message='Could not finish',error=message[:300])


def state(job):
    row=db.query('SELECT * FROM jobs WHERE id=?',(job,),one=True)
    if row and row.get('result_json'):
        row['result']=json.loads(row.pop('result_json'))
    return row


def audio_job(key,task,*args):
    with _lock:
        job=_audio_jobs.get(key)
        if job:
            status=state(job)
            if status and status['state']!='error':
                return job
        job=enqueue('audio',task,*args)
        _audio_jobs[key]=job
        return job
