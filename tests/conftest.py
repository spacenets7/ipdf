import pytest
import time
from unittest.mock import Mock
from app import db
from app.config import settings
from app import auth
real_account=auth.account


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'data_dir', tmp_path)
    monkeypatch.setenv('LLM_API_KEY','mock-key')
    monkeypatch.setenv('LLM_MODEL','mock-model')
    for name in ('DEEP_BASE_URL','DEEP_API_KEY','DEEP_MODEL'):
        monkeypatch.delenv(name,raising=False)
    db.init_db()
    db.execute("INSERT INTO accounts(id,login) VALUES(?,?)",('test-user','test-reader'))
    monkeypatch.setattr(auth,'account',lambda request:{'id':'test-user','login':'test-reader'})
    monkeypatch.setattr('app.llm.OpenAI',Mock(side_effect=AssertionError('Tests must mock hosted inference')))
    yield
    # Let automatically queued preparation finish before changing the database path.
    for _ in range(100):
        if not db.query("SELECT 1 FROM jobs WHERE state IN ('queued','running') LIMIT 1",one=True):break
        time.sleep(.03)
