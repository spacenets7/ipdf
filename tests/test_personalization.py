from unittest.mock import patch
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from app.main import app
from app.schema import ReaderProfile,Flashcard
from app.orchestrate import cache_key
from app.audio import create_audio
from app.config import settings


def test_reader_profiles_do_not_share_editions():
    base=ReaderProfile().model_dump()
    assert cache_key('paper','beginner',base)!=cache_key('paper','beginner',base|{'goal':'critique'})
    assert cache_key('paper','beginner',base)!=cache_key('paper','beginner',base|{'background':'Python'})


def test_invalid_profile_rejected_before_generation():
    with TestClient(app) as client:
        for data in ({'goal':'invent'},{'minutes':'0'},{'background':'x'*301},{'voice':'local'}):
            assert client.post('/ipdf/create',data={'arxiv_id':'1706.03762',**data}).status_code==422


def test_quiz_must_have_one_valid_answer():
    card=dict(id='q',front='Question',back='Evidence',section_id='s',page=1,
        generated_by=dict(plugin='cards',prompt_version='test',model='mock',source_page=1))
    for choices,index in [(['a','a'],0),(['a','b'],2),(['a'],0),([],0)]:
        with pytest.raises(ValidationError):
            Flashcard(**card,choices=choices,correct_index=index)


def test_character_budget_falls_back_without_provider_call(monkeypatch):
    monkeypatch.setenv('TTS_CHARACTER_BUDGET','5')
    monkeypatch.setattr(settings,'eleven_key','mock')
    monkeypatch.setattr(settings,'eleven_voice','mock')
    with patch('app.audio.httpx.Client',side_effect=AssertionError('No network')):
        assert create_audio('Longer than five characters',provider='elevenlabs')['provider']=='browser'
