import json
from pydantic import BaseModel, Field
from app.extract import select_text
from app.llm import chat_json, LLMError
from app.modules.digest.summarize import summarize


class Verdict(BaseModel):
    passed: bool
    reasons: list[str] = Field(max_length=12)


def judge(item, summary):
    if len(summary.model_dump_json().split()) > 450:
        return Verdict(passed=False,reasons=['Summary exceeds 450 words'])
    try:
        return chat_json(Verdict,
            'Judge this summary against ONLY the source. Check every factual claim, number and limitation. '
            'Speculation presented as fact must fail. An explicit statement that evidence is missing is allowed. '
            'Check TLDR is at most two sentences and key_points has exactly three entries. '
            'passed is true only if grounded and concise. reasons describes unsupported claims.\n'
            'SUMMARY:\n'+summary.model_dump_json()+'\nSOURCE:\n'+select_text(item['raw_text']),
            backend='DEEP',purpose='judge').value
    except LLMError:
        return Verdict(passed=False,reasons=['Grounding judge unavailable'])


def verified_summary(item, level):
    result = summarize(item,level)
    verdict = judge(item,result.value)
    if not verdict.passed:
        result = summarize(item,level,{'correction':json.dumps(verdict.reasons)},force=True)
        verdict = judge(item,result.value)
    return result,verdict
