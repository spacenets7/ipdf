import json
import pytest
from app import db
from app.modules.digest.feedback import apply_feedback
from app.modules.digest.levels import shift_level
from app.modules.digest.sources.base import Item


def seed():
    db.execute('INSERT INTO users(id,name,level,topics_json,topic_weights_json) VALUES(?,?,?,?,?)',
               ('reader','Reader','intermediate','["machine learning"]','{}'))
    return [db.upsert_item(Item(source='arxiv',external_id=str(i),title='Machine learning',authors=[],
              url='https://arxiv.org/abs/1',published='2026-10-23',raw_text='Source',tags=['cs.LG']))['id'] for i in range(3)]


def test_difficulty_crosses_threshold_and_resets():
    items = seed()
    assert apply_feedback('reader',items[0],'too_hard')['level_offset'] == -.25
    result = apply_feedback('reader',items[1],'too_hard')
    assert (result['level'],result['level_offset']) == ('beginner',0)
    assert shift_level('expert',.25,'too_easy') == ('expert',0)


def test_weights_and_duplicate_protection():
    item = seed()[0]
    result = apply_feedback('reader',item,'up')
    assert result['topic_weights']['cs.LG'] == 1.1
    assert result['topic_weights']['machine learning'] == 1.1
    assert apply_feedback('reader',item,'up')['duplicate']
    result = apply_feedback('reader',item,'down')
    assert result['topic_weights']['cs.LG'] == 1
    with pytest.raises(ValueError):
        apply_feedback('reader',item,'invalid')
