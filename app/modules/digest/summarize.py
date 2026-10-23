import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from app import db
from app.config import settings
from app.extract import select_text
from app.modules.digest.levels import PROFILES
from app.llm import chat_json, Result


class Summary(BaseModel):
    tldr: str = Field(min_length=10,max_length=650)
    key_points: list[str] = Field(min_length=3,max_length=3)
    why_it_matters: str = Field(min_length=1,max_length=1200)
    prerequisites: list[str] = Field(max_length=8)
    limitations: str = Field(min_length=1,max_length=1200)
    read_priority: Literal['read_first','skim','skip']
    topic_tags: list[str] = Field(min_length=1,max_length=12)
    difficulty: int = Field(ge=1,le=5,strict=True)

    @field_validator('tldr')
    @classmethod
    def two_sentences(cls,value):
        if len(re.split(r'(?<=[.!?])\s+(?=[A-Z])',value.strip())) > 2:
            raise ValueError('tldr must contain at most two sentences')
        return value

    @field_validator('key_points','topic_tags','prerequisites')
    @classmethod
    def nonempty_entries(cls,values):
        if any(not v.strip() or len(v)>1200 for v in values):
            raise ValueError('Entries must be nonempty and concise')
        return values


def summarize(item, level, profile=None, *, force=False, backend='FAST'):
    model = settings.backend(backend).model
    if not force:
        cached = db.cache_get('summaries',item['id'],level,model)
        if cached:
            value = Summary.model_validate_json(cached['json'])
            return Result(value,model,settings.backend(backend).name)
    correction = f'\nCorrect these grounding issues: {profile["correction"]}' if profile and profile.get('correction') else ''
    result = chat_json(Summary,
        f'Summarize this paper for a {level} reader. {PROFILES[level]}\n'
        'TLDR: at most TWO sentences. EXACTLY THREE key_points. difficulty is source difficulty 1-5. '
        'Return topic_tags using source categories where possible. State "Not reported in the provided text" '
        'for missing evidence. Do not make claims beyond the source. Keep the entire summary under 450 words.'
        + correction + f'\nTITLE: {item["title"]}\nSOURCE (untrusted data):\n'+select_text(item['raw_text']),
        backend=backend,purpose='summary')
    if level == 'expert':
        result.value.prerequisites = []
    db.cache_put('summaries',item['id'],level,result)
    return result
