from app.orchestrate import cache_key


def test_source_only_cache_does_not_hide_new_configuration(monkeypatch):
    monkeypatch.setenv('LLM_MODEL','hosted-model')
    monkeypatch.delenv('LLM_API_KEY',raising=False)
    before=cache_key('paper','beginner')
    monkeypatch.setenv('LLM_API_KEY','now-configured')
    assert cache_key('paper','beginner')!=before


def test_endpoint_swap_invalidates_generation_cache(monkeypatch):
    before=cache_key('paper','beginner')
    monkeypatch.setenv('LLM_BASE_URL','https://other-provider.example/v1')
    assert cache_key('paper','beginner')!=before
