from unittest.mock import patch
from app import db
from app.config import settings
from app.modules.digest.digest import build_digest
from app.modules.digest.judge import Verdict, verified_summary
from app.llm import Result
from app.modules.digest.summarize import Summary
from app.modules.digest.sources.base import Item
from test_summary import SAMPLE


def test_judge_regenerates_once_and_marks_unverified():
    result = Result(Summary(**SAMPLE),'model','FAST')
    with patch('app.modules.digest.judge.summarize',return_value=result) as generate, \
         patch('app.modules.digest.judge.judge',return_value=Verdict(passed=False,reasons=['unsupported number'])):
        _,verdict=verified_summary({'id':1},'beginner')
    assert not verdict.passed
    assert generate.call_count == 2
    assert generate.call_args.kwargs['force']


def test_offline_digest_persists_and_loads_without_generation(monkeypatch):
    monkeypatch.setattr(settings,'offline',True)
    monkeypatch.setattr(settings,'deep_top_k',0)
    db.execute('INSERT INTO users(id,name,level,topics_json,topic_weights_json) VALUES(?,?,?,?,?)',
               ('reader','Reader','intermediate','["cs.AI"]','{}'))
    item=db.upsert_item(Item(source='arxiv',external_id='test:1',title='AI paper',authors=[],
         url='https://arxiv.org/abs/1',published='2026-10-23',raw_text='Paper evidence',tags=['cs.AI']))
    result=Result(Summary(**SAMPLE),'local','FAST')
    with patch('app.modules.digest.digest.verified_summary',return_value=(result,Verdict(passed=True,reasons=[]))):
        digest=build_digest(db.get_user('reader'))
    assert len(digest['rows']) == 1
    assert digest['rows'][0]['verified']
    assert 'Offline mode' in digest['markdown']
    with patch('app.modules.digest.digest.verified_summary',side_effect=AssertionError('Should use cache')):
        assert build_digest(db.get_user('reader'))['id'] == digest['id']
