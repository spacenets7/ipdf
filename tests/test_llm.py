from types import SimpleNamespace as NS
from unittest.mock import MagicMock
import pytest
from pydantic import BaseModel
from app.llm import chat_json, parse_json, LLMError
from app.config import settings
from app import db
import httpx
from openai import AuthenticationError,APIStatusError
from app.llm import ConfigurationError,ProviderUnavailable


class Answer(BaseModel):
    answer: int


def reply(text):
    return NS(usage=NS(prompt_tokens=10,completion_tokens=5),choices=[NS(message=NS(content=text))])


def test_repairs_and_tracks_all_attempts():
    client = MagicMock()
    client.chat.completions.create.side_effect = [reply('{"answer":"bad"}'),reply('<think>secret</think>```json\n{"answer":42,}\n```')]
    result = chat_json(Answer,'answer',client=client)
    assert result.value.answer == 42
    assert result.prompt_tokens == 20
    assert len(db.query('SELECT * FROM usage')) == 2
    assert client.chat.completions.create.call_args.kwargs['temperature'] == 0.2


def test_bounded_retries():
    client = MagicMock()
    client.chat.completions.create.return_value = reply('invalid')
    with pytest.raises(LLMError):
        chat_json(Answer,'answer',client=client)
    assert client.chat.completions.create.call_count == 3


def test_deep_requires_complete_configuration(monkeypatch):
    for name in ('DEEP_BASE_URL','DEEP_API_KEY','DEEP_MODEL'):
        monkeypatch.delenv(name,raising=False)
    assert settings.backend('DEEP') == settings.backend('FAST')
    monkeypatch.setenv('DEEP_BASE_URL','http://example.test/v1')
    assert settings.backend('DEEP').name == 'FAST'


def test_no_execution_in_json_repair():
    with pytest.raises(ValueError):
        parse_json('__import__("os").system("echo unsafe")')


def test_bad_hosted_key_fails_fast():
    client=MagicMock()
    response=httpx.Response(401,request=httpx.Request('POST','https://example.test/v1/chat/completions'))
    client.chat.completions.create.side_effect=AuthenticationError('Rejected',response=response,body=None)
    with pytest.raises(ConfigurationError):
        chat_json(Answer,'answer',client=client)
    assert client.chat.completions.create.call_count==1


def test_exhausted_provider_credits_fail_fast_with_actionable_message():
    client=MagicMock()
    response=httpx.Response(402,request=httpx.Request('POST','https://example.test/v1/chat/completions'))
    client.chat.completions.create.side_effect=APIStatusError('Payment required',response=response,body=None)
    with pytest.raises(ConfigurationError,match='no remaining inference credits'):
        chat_json(Answer,'answer',client=client)
    assert client.chat.completions.create.call_count==1


def test_rate_limit_honors_retry_after(monkeypatch):
    delays=[]
    monkeypatch.setattr('app.llm.time.sleep',delays.append)
    client=MagicMock()
    response=httpx.Response(429,headers={'retry-after':'3'},request=httpx.Request('POST','https://example.test/v1/chat/completions'))
    client.chat.completions.create.side_effect=[APIStatusError('Slow down',response=response,body=None),reply('{"answer":42}')]
    assert chat_json(Answer,'answer',client=client).value.answer==42
    assert delays==[3]


def test_grounding_outage_does_not_regenerate_paid_output():
    client=MagicMock()
    client.chat.completions.create.return_value=reply('{"answer":42}')
    def unavailable(value):
        raise ProviderUnavailable('Wait for the rate limit')
    with pytest.raises(ProviderUnavailable):
        chat_json(Answer,'answer',client=client,validate=unavailable)
    assert client.chat.completions.create.call_count==1


def test_long_quota_reset_stops_job_without_sleeping(monkeypatch):
    delays=[]
    monkeypatch.setattr('app.llm.time.sleep',delays.append)
    client=MagicMock()
    response=httpx.Response(429,headers={'retry-after':'3600'},request=httpx.Request('POST','https://example.test/v1/chat/completions'))
    client.chat.completions.create.side_effect=APIStatusError('Quota',response=response,body=None)
    with pytest.raises(ProviderUnavailable):
        chat_json(Answer,'answer',client=client)
    assert not delays
    assert client.chat.completions.create.call_count==1
