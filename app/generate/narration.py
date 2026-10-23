import re
from pydantic import BaseModel,Field
from app.schema import Narration
from app.generate.common import generate,provenance


class NarrationOutput(BaseModel):
    script: str=Field(min_length=20,max_length=3000)
    simpler_script: str=Field(min_length=20,max_length=1200)


def build(section,level,paper_id):
    def validate(value):
        for script in (value.script,value.simpler_script):
            if re.search(r'```|\$|^\s*[#*•]|\\(?:frac|sum|begin)\b',script,re.M):
                raise ValueError('Narration must be plain spoken English, no Markdown or equations')
    result=generate(NarrationOutput,'narration',section,level,paper_id,
        'Write a spoken walkthrough of this section, preserving its scope and uncertainty. Short sentences, '
        'no markdown, no equations, describe equations in words. It must fit the reader level. '
        'Also provide a distinctly simpler and shorter replay script. Do not produce a global paper summary. '
        'Stay under 3000 characters for script and 1200 for simpler_script. Intro/outro lines will be added by the app.',validator=validate)
    intro=f'You are listening to {section.title[:100]}, page {section.page}. '
    outro=' That is the end of this section. Continue when you are ready.'
    return [Narration(section_id=section.id,page=section.page,script=intro+result.value.script+outro,
        simpler_script='Let us take this one step at a time. '+result.value.simpler_script+outro,audio_url=None,
        generated_by=provenance('narration',section.page,result))]
