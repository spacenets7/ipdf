import re
from pydantic import BaseModel,Field
from app.schema import Glossary
from app.generate.common import generate,provenance


class Entry(BaseModel):
    term: str=Field(min_length=2,max_length=100)
    definition: str=Field(min_length=5,max_length=1000)


class GlossaryOutput(BaseModel):
    entries: list[Entry]=Field(max_length=5)


def build(section,level,paper_id):
    def validate(value):
        source=' '.join(section.text.lower().split())
        for entry in value.entries:
            if ' '.join(entry.term.lower().split()) not in source:
                raise ValueError('Glossary term must occur literally on the source page: '+entry.term)
    result=generate(GlossaryOutput,'glossary',section,level,paper_id,
        'Choose up to FIVE useful terms that occur literally on this page. Define their meaning in the context '
        'of the paper. For experts use fewer, deeper definitions; for beginners explain concepts simply. '
        'An empty entries array is valid for references-only pages.',validator=validate)
    return [Glossary(term=e.term,definition=e.definition,section_id=section.id,page=section.page,
        generated_by=provenance('glossary',section.page,result)) for e in result.value.entries]
