import pytest
from app import db
from app.config import settings


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'data_dir', tmp_path)
    monkeypatch.setenv('LLM_API_KEY','mock-key')
    monkeypatch.setenv('LLM_MODEL','mock-model')
    for name in ('DEEP_BASE_URL','DEEP_API_KEY','DEEP_MODEL'):
        monkeypatch.delenv(name,raising=False)
    db.init_db()
