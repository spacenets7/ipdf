import pytest
from pydantic import ValidationError
from app.modules.digest.summarize import Summary

SAMPLE = dict(tldr='The paper studies a new method.', key_points=['One','Two','Three'],
 why_it_matters='It may help readers.',prerequisites=[],limitations='Abstract only.',
 read_priority='skim',topic_tags=['cs.AI'],difficulty=3)


def test_schema_constraints():
    Summary(**SAMPLE)
    for bad in ({'difficulty':6},{'key_points':['One']},{'tldr':'One sentence. Second sentence. Third sentence.'}):
        with pytest.raises(ValidationError):
            Summary(**(SAMPLE|bad))
