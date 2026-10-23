import json
import time
from unittest.mock import patch,Mock
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app import db,auth,jobs,tutor
from app.main import app
from app.schema import IPDF
from app.llm import Result
from conftest import real_account
from test_schema import document

def seed():
    doc=IPDF(**document());doc.meta.paper_id='a'*64
    db.execute('INSERT INTO ipdfs(id,paper_id,level,model,cache_key,json) VALUES(?,NULL,?,?,?,?)',('private','beginner','mock','private',doc.model_dump_json()))
    db.execute('INSERT INTO document_access(document_id,account_id) VALUES(?,?)',('private','test-user'))
    return doc

def test_private_routes_and_media_deny_other_accounts(monkeypatch):
    doc=seed()
    with TestClient(app) as client:
        assert client.get('/ipdf/private').status_code==200
        monkeypatch.setattr(auth,'account',lambda request:{'id':'intruder','login':'other'})
        for path in ['/ipdf/private','/ipdf/private.json','/ipdf/private/export','/api/tutor/private','/media/papers/'+'a'*64+'.pdf']:
            assert client.get(path).status_code==404,path
        assert client.post('/api/papers/private/sharing',json={'public':True}).status_code==404
        assert client.post('/api/tutor/private/ask',json={'section_id':'p1','question':'Why?'}).status_code==404

def test_anonymous_public_reader_cannot_use_paid_tools(monkeypatch):
    seed();db.execute('UPDATE document_access SET public=1')
    monkeypatch.setattr(auth,'account',lambda request:None)
    with TestClient(app) as client:
        assert client.get('/ipdf/private').status_code==200
        assert client.post('/ipdf/create',data={'arxiv_id':'1706.03762'}).status_code==401
        assert client.get('/api/library').status_code==401
        assert client.post('/api/tutor/private/ask',json={'section_id':'p1','question':'Explain this'}).status_code==401

def test_session_expiry_logout_and_missing_oauth_state(monkeypatch):
    monkeypatch.setattr(auth,'account',real_account)
    db.execute('INSERT INTO sessions VALUES(?,?,?)',(auth.digest('valid'),'test-user',time.time()+300))
    with TestClient(app) as client:
        assert client.get('/api/library').status_code==401
        client.cookies.set(auth.COOKIE,'valid')
        assert client.get('/api/library').status_code==200
        assert client.get('/auth/github/callback?code=bad&state=bad').status_code==400
        assert client.post('/auth/logout',follow_redirects=False).status_code==303
        assert client.get('/api/library').status_code==401

def test_oauth_state_and_pkce_are_bound_to_browser(monkeypatch):
    monkeypatch.setenv('GITHUB_CLIENT_ID','client');monkeypatch.setenv('GITHUB_CLIENT_SECRET','secret')
    with TestClient(app) as client:
        response=client.get('/auth/github',follow_redirects=False)
        assert response.status_code==307
        assert 'code_challenge_method=S256' in response.headers['location']
        assert 'httponly' in response.headers['set-cookie'].lower()
        assert client.get('/auth/github/callback?code=bad&state=wrong').status_code==400
    assert len(db.query('SELECT * FROM oauth_states'))==1

def test_oauth_callback_creates_opaque_session_without_storing_github_token(monkeypatch):
    from urllib.parse import urlparse,parse_qs
    monkeypatch.setattr(auth,'account',real_account)
    monkeypatch.setenv('GITHUB_CLIENT_ID','client');monkeypatch.setenv('GITHUB_CLIENT_SECRET','secret')
    with TestClient(app) as client:
        response=client.get('/auth/github',follow_redirects=False)
        state=parse_qs(urlparse(response.headers['location']).query)['state'][0]
        github=Mock();github.post.return_value.json.return_value={'access_token':'github-secret-not-a-session'}
        github.get.return_value.json.return_value={'id':123,'login':'reader'}
        with patch('app.auth.httpx.Client') as factory:
            factory.return_value.__enter__.return_value=github
            result=client.get('/auth/github/callback',params={'code':'valid','state':state},follow_redirects=False)
        assert result.status_code==303
        assert 'github-secret' not in result.headers.get('set-cookie','')
        assert client.get('/api/library').status_code==200
        assert not db.query('SELECT * FROM oauth_states')
        assert 'github-secret' not in str(db.query('SELECT * FROM sessions'))

def test_reading_position_and_memory_are_private():
    seed()
    with TestClient(app) as client:
        assert client.post('/api/papers/private/position',json={'section_id':'p1','speed':1.25,'offset':37}).status_code==200
        assert client.get('/api/papers/private/position').json()['offset']==37
        assert client.post('/api/papers/private/position',json={'section_id':'missing','speed':1}).status_code==422

def test_concept_map_rejects_cycles_and_missing_prerequisites():
    def c(name,deps):return dict(name=name,explanation='A supported concept',depends_on=deps,section_id='p1',page=1,source_quote='Source passage')
    for values in [[c('A',['B']),c('B',['A'])],[c('A',['missing'])]]:
        with pytest.raises(ValidationError):tutor.ConceptMap(concepts=values)

def test_prerequisite_map_validates_source_and_saves_private_result():
    seed();mapping=tutor.ConceptMap(concepts=[dict(name='Evidence',explanation='The page discusses evidence.',section_id='p1',page=1,source_quote='Evidence here')])
    # Make the quote long enough and actually present, then assert invalid quotes fail validation.
    row=db.query('SELECT json FROM ipdfs WHERE id=?',('private',),one=True);data=json.loads(row['json']);data['sections'][0]['text']='Evidence here comes from the paper.'
    db.execute('UPDATE ipdfs SET json=? WHERE id=?',(json.dumps(data),'private'))
    def chat(schema,prompt,**kwargs):
        kwargs['validate'](mapping);return Result(mapping,'mock','FAST')
    db.execute("INSERT INTO jobs(id,kind,state) VALUES('map','prepare','running')")
    with patch('app.tutor.chat_json',side_effect=chat),patch('app.tutor.grounded'):
        tutor.prepare('map','private','test-user')
    assert jobs.state('map')['state']=='ready'
    assert db.query('SELECT * FROM tutor_maps',one=True)['account_id']=='test-user'

def test_restart_requeues_serialized_jobs_without_browser():
    db.execute("INSERT INTO jobs(id,kind,state,args_json,attempts) VALUES('resume','create','running',?,1)",(json.dumps([None,'1706.03762','beginner',{},'test-user']),))
    with patch.object(jobs._pool,'submit') as submit:
        jobs.recover()
    assert jobs.state('resume')['state']=='queued'
    assert submit.call_count==1
    db.execute("UPDATE jobs SET state='error' WHERE id='resume'")
