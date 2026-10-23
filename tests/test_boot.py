from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

def test_boots_without_keys_or_models(monkeypatch):
    monkeypatch.delenv('LLM_BASE_URL',raising=False)
    monkeypatch.delenv('LLM_API_KEY',raising=False)
    monkeypatch.delenv('LLM_MODEL',raising=False)
    with TestClient(app) as client:
        result=client.get('/health')
    assert result.status_code==200
    assert not result.json()['llm_configured']
    assert settings.backend().base_url=='https://router.huggingface.co/v1'
