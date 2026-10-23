from pydantic import BaseModel,Field
from app.schema import Flashcard
from app.generate.common import generate,provenance


class Card(BaseModel):
    front: str=Field(min_length=5,max_length=400)
    back: str=Field(min_length=5,max_length=1600)


class CardsOutput(BaseModel):
    cards: list[Card]=Field(max_length=3)


def build(section,level,paper_id):
    result=generate(CardsOutput,'flashcards',section,level,paper_id,
        'Create up to THREE self-contained question-and-answer study cards from this page. '
        'Beginner: basic understanding. Intermediate: methods and connections. Expert: assumptions and implications '
        'supported by the text. Never ask a question whose answer is absent from this source. '
        'An empty cards array is valid for references-only pages.')
    return [Flashcard(id=f'{section.id}-card-{i+1}',front=c.front,back=c.back,section_id=section.id,
        page=section.page,generated_by=provenance('flashcards',section.page,result)) for i,c in enumerate(result.value.cards)]
