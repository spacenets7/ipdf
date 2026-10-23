import json
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app import db
from app.main import app
from app.modules.digest.sources.base import Item
from test_summary import SAMPLE


@pytest.fixture
def client():
    with patch('app.main.schedule'):
        with TestClient(app) as client:
            yield client


def profile(client):
    response=client.post('/start',data={'name':'Reader','level':'beginner','topics':'cs.AI'},follow_redirects=False)
    assert response.status_code==303
    return db.get_user(client.cookies.get('user_id'))


def saved_digest(client):
    user=profile(client)
    item=db.upsert_item(Item(source='arxiv',external_id='paper:1',title='<script>unsafe</script>',
        url='https://arxiv.org/abs/1',published='2026-10-23',raw_text='Source evidence',tags=['cs.AI']))
    row={'item':item,'summary':SAMPLE,'model':'local','level':'beginner','verified':False,'verification_reasons':['uncertain']}
    db.execute('INSERT INTO digests(user_id,date,markdown,payload_json) VALUES(?,?,?,?)',
               (user['id'],'2026-10-23','# Digest',json.dumps([row])))
    return user,item


def test_form_cookie_digest_download_and_feedback(client):
    assert client.get('/').status_code==200
    assert client.get('/digest',follow_redirects=False).status_code==303
    user,item=saved_digest(client)
    page=client.get('/digest')
    assert page.status_code==200
    assert '&lt;script&gt;unsafe&lt;/script&gt;' in page.text
    assert client.get('/digest.md').text=='# Digest'
    assert client.post('/feedback',json={'item_id':item['id'],'signal':'up'}).status_code==200
    assert client.post('/feedback',json={'item_id':item['id'],'signal':'invalid'}).status_code==422
    assert client.post('/feedback',json={'item_id':999,'signal':'up'}).status_code==404
    assert client.get('/digest/status').status_code==200
    assert client.post('/digest/refresh').status_code==200


def test_audio_routes_and_owned_files(client,tmp_path):
    from app.audio import AudioError
    user,item=saved_digest(client)
    with patch('app.audio.create_audio',side_effect=AudioError('Voice unavailable')):
        assert client.post(f'/audio/{item["id"]}?level=beginner').status_code==503
        assert client.post('/audio/digest').status_code==503
    assert client.post('/audio/999').status_code==404
    assert client.get('/audio/file/not-a-hash.mp3').status_code==404
    assert client.get('/audio/file/'+('a'*64)+'.mp3').status_code==404
    assert client.post(f'/audio/{item["id"]}?level=invalid').status_code==422


def test_profile_validation_and_cross_origin(client):
    assert client.post('/start',data={'name':'Reader','level':'beginner'}).status_code==422
    assert client.post('/start',data={'name':'Reader','topics':'cs.AI'},headers={'Origin':'https://other.example'}).status_code==403
    assert client.post('/feedback',json={'item_id':1,'signal':'up'}).status_code==401


def test_health_checks_dependencies(client):
    with patch('app.main.httpx.Client') as http:
        http.return_value.__enter__.return_value.get.side_effect=ConnectionError()
        health=client.get('/health')
    assert health.status_code==200
    assert not health.json()['local_model_ready']
