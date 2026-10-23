from typing import Literal
from pydantic import BaseModel, Field
from app import db
from app.config import settings
from app.extract import chunks, enrich
from app.modules.digest.levels import PROFILES
from app.llm import chat_json, Result


class Analysis(BaseModel):
    problem: str = Field(min_length=1)
    core_idea: str = Field(min_length=1)
    method_steps: list[str]
    key_results: list[str]
    assumptions: list[str]
    limitations: list[str]
    related_work_gaps: str
    reproduction_checklist: list[str]
    open_questions: list[str]
    confidence: Literal['high','medium','low']


def analyze(item, level, *, force=False):
    chosen = settings.backend('DEEP')
    if not force:
        for model in dict.fromkeys((chosen.model,settings.backend('FAST').model)):
            cached = db.cache_get('analyses',item['id'],level,model)
            if cached:
                return Result(Analysis.model_validate_json(cached['json']),model,
                              'DEEP' if model == chosen.model and chosen.name == 'DEEP' else 'FAST')
    text = enrich(item,full=True)
    item['raw_text'] = text
    instruction = (f'Analyze this paper for a {level} reader. {PROFILES[level]} '
        'Use ONLY supported claims; reference section names where available. Include numerical results ONLY if present, '
        'preserving exact numbers and their context. Distinguish author-stated assumptions from unanswered questions. '
        'If only an abstract is available, state that limitation and use low confidence. Missing information must be '
        'explicitly marked "Not reported in provided text". Reproduction checklist should distinguish stated procedures '
        'from suggested checks. Keep each field concise.\n')
    parts = list(chunks(text))
    results = [chat_json(Analysis,instruction+f'TITLE: {item["title"]}\nSOURCE PART {i+1}/{len(parts)}:\n'+part,
                         backend='DEEP',purpose='deep') for i,part in enumerate(parts)]
    if len(results) == 1:
        result = results[0]
    else:
        evidence = '\n'.join(f'Part {i+1}: '+r.value.model_dump_json() for i,r in enumerate(results))
        result = chat_json(Analysis,instruction+'Merge these evidence-bound analyses of sections from the same paper. '
                           'Deduplicate; do not invent cross-section conclusions.\n'+evidence,backend='DEEP',purpose='deep_merge')
        result.prompt_tokens += sum(r.prompt_tokens for r in results)
        result.completion_tokens += sum(r.completion_tokens for r in results)
        result.cost += sum(r.cost for r in results)
    db.cache_put('analyses',item['id'],level,result)
    return result
