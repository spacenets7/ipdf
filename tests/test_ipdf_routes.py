import json
import time
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import db
from app.main import app
from app.schema import IPDF
from app.render.pages import export_html
from test_ingest import make_pdf
from test_schema import document


def wait(client,job):
    for _ in range(200):
        state=client.get('/ipdf/status/'+job).json()
        if state['state'] in ('ready','error'):
            return state
        time.sleep(.02)
    raise AssertionError('Background job did not finish')


def test_upload_background_source_only_view_and_exports(monkeypatch):
    monkeypatch.delenv('LLM_API_KEY',raising=False)
    monkeypatch.delenv('LLM_MODEL',raising=False)
    with TestClient(app) as client:
        assert client.get('/').status_code==200
        response=client.post('/ipdf/create',files={'pdf':('paper.pdf',make_pdf(),'application/pdf')},data={'level':'beginner'})
        assert response.status_code==202
        state=wait(client,response.json()['job_id'])
        assert state['state']=='ready',state
        paper_id=state['result_id']
        page=client.get('/ipdf/'+paper_id)
        assert page.status_code==200
        assert 'ipdf-data' in page.text
        raw=client.get('/ipdf/'+paper_id+'.json')
        parsed=IPDF.model_validate(raw.json())
        assert len(parsed.sections)==2
        assert not parsed.glossary
        assert parsed.issues[0].plugin in ('ingest','configuration')
        exported=client.get('/ipdf/'+paper_id+'/export')
        assert exported.status_code==200
        assert 'src="/static/' not in exported.text
        assert 'data:application/pdf;base64,' in exported.text
        assert client.get('/media/papers/'+parsed.meta.paper_id+'.pdf').status_code==200
        assert client.post(f'/audio/{paper_id}/p1').status_code==404


def test_validation_and_missing_routes():
    with TestClient(app) as client:
        assert client.post('/ipdf/create').status_code==422
        assert client.post('/ipdf/create',data={'arxiv_id':'http://127.0.0.1/a'}).status_code==422
        assert client.post('/ipdf/create',data={'arxiv_id':'1706.03762','level':'wrong'}).status_code==422
        assert client.post('/ipdf/create',files={'pdf':('bad.pdf',b'not-pdf')}).status_code==422
        assert client.get('/ipdf/status/missing').status_code==404
        assert client.get('/ipdf/missing').status_code==404
        assert client.get('/media/audio/nope.mp3').status_code==404


def test_export_escapes_untrusted_source():
    data=document()
    data['sections'][0]['text']='</script><script>alert(1)</script>'
    html=export_html(IPDF(**data))
    assert '\\u003c/script\\u003e' in html
    assert '</script><script>alert(1)' not in html
