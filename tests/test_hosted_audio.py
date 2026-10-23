from unittest.mock import patch,MagicMock
from app.audio import create_audio
from app.config import settings


def test_browser_fallback_needs_no_provider(monkeypatch):
    monkeypatch.setattr(settings,'tts_provider','browser')
    with patch('app.audio.httpx.Client',side_effect=AssertionError('No network')):
        assert create_audio('A section narration.')['provider']=='browser'


def test_eleven_failure_uses_browser(monkeypatch):
    monkeypatch.setattr(settings,'tts_provider','elevenlabs')
    monkeypatch.setattr(settings,'eleven_key','mock')
    monkeypatch.setattr(settings,'eleven_voice','voice')
    with patch('app.audio.httpx.Client') as http:
        http.return_value.__enter__.return_value.post.side_effect=ConnectionError('Quota unavailable')
        result=create_audio('A section narration.')
    assert result['provider']=='browser'
    assert 'unavailable' in result['message']


def test_audio_cache_avoids_second_provider_call(monkeypatch):
    monkeypatch.setattr(settings,'tts_provider','elevenlabs')
    monkeypatch.setattr(settings,'eleven_key','mock')
    monkeypatch.setattr(settings,'eleven_voice','voice')
    response=MagicMock(content=b'mock-mp3',headers={'content-type':'audio/mpeg'})
    with patch('app.audio.httpx.Client') as http:
        http.return_value.__enter__.return_value.post.return_value=response
        first=create_audio('A section narration.')
        second=create_audio('A section narration.')
    assert not first['cached'] and second['cached']
    assert http.return_value.__enter__.return_value.post.call_count==1
