import pytest
from unittest.mock import patch
from app import db
from app.audio import split_script,create_audio,AudioError
from app.config import settings


def test_chunking_bounds_and_content():
    text='First sentence. Second sentence is longer. '+('x'*51)
    chunks=split_script(text,20)
    assert all(0<len(c)<=20 for c in chunks)
    assert ''.join(''.join(chunks).split())==''.join(text.split())
    with pytest.raises(ValueError):
        split_script(text,0)


def test_eleven_failure_falls_back_and_exposes_message(monkeypatch):
    monkeypatch.setattr(settings,'tts_provider','elevenlabs')
    monkeypatch.setattr(settings,'eleven_key','test-key')
    monkeypatch.setattr(settings,'eleven_voice','voice')
    monkeypatch.setattr(settings,'offline',False)
    with patch('app.audio.narration_script',return_value='Paper: A. Test narration.'), \
         patch('app.audio._render',side_effect=[AudioError('Quota reached; using local.'),{'provider':'local','hash':'test'}]) as render:
        result=create_audio({'level':'beginner'})
    assert result['provider']=='local'
    assert 'Quota' in result['message']
    assert render.call_args.args[1]=='local'
