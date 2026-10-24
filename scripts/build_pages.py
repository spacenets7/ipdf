"""Build the public static reader. Never reads runtime data or provider keys."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import ROOT
from app.schema import IPDF
from app.render.pages import export_html, safe_json

def build():
    destination=ROOT/'docs'
    destination.mkdir(exist_ok=True)
    authored=lambda plugin:dict(plugin=plugin,prompt_version='authored-demo/0.2.0',model='authored format demonstration',source_page=1)
    paper=IPDF.model_validate(dict(
        meta=dict(title='Welcome to iPDF',authors=['iPDF'],source_url='https://github.com/spacenets7/ipdf/blob/main/SPEC.md',level='beginner'),
        sections=[dict(id='welcome',title='A paper with more ways in',page=1,text=
            'iPDF keeps the original paper at the center. A glossary explains unfamiliar terms. Flashcards let you check an idea and save it for later. Narration explains one section at a time, so you can listen while walking.\n\nProvenance records where a learning block came from: its source page, model and prompt version. The viewer reads the finished JSON and never calls an AI model. Generation happens separately in the full app.\n\nThis is an authored format demonstration, not generated research output. Tap glossary, flashcards or provenance in the text, open a study card, or press Listen to paper to try browser speech. No source table is included, so there is no chart.')],
        glossary=[dict(term=term,definition=definition,section_id='welcome',page=1,generated_by=authored('glossary')) for term,definition in [
            ('glossary','A collection of explanations for terms used in the source text.'),
            ('flashcards','Questions and answers that help you check understanding and revisit an idea.'),
            ('provenance','The source page, model and prompt version attached to a learning block.')]],
        flashcards=[dict(id='demo-card',front='Does the viewer call an AI model?',back='No. It renders the completed iPDF JSON. Generation runs separately in the full application.',section_id='welcome',page=1,choices=['Yes, for every page','No, it only reads the JSON'],correct_index=1,generated_by=authored('flashcards')),
            dict(id='demo-evidence',front='Why is there no chart in this sample?',back='There is no source table. Charts must use numbers parsed from the original paper tables; missing evidence means no chart.',section_id='welcome',page=1,generated_by=authored('flashcards'))],
        narration=[dict(section_id='welcome',page=1,script='Welcome to iPDF. This is an authored demonstration of the format. The original text stays at the center. Tap a term to learn its meaning. Open a flashcard to check your understanding. Each explanation keeps its source page and provenance. The viewer reads a finished document. It does not call a model. You can export the edition and read it elsewhere. That is the end of this short example. Bring your next paper when you are ready.',simpler_script='Welcome. iPDF is a paper with extra ways to learn. Tap words for meanings. Open cards for questions. Press play to listen. Everything in this example was written as a format guide. That is all for now.',generated_by=authored('narration'))],
        provenance=dict(model='authored demonstration',prompt_versions={},generated_at='2026-10-23T00:00:00Z')))
    html=export_html(paper)
    (destination/'demo.html').write_text(html,encoding='utf-8')
    (destination/'demo.ipdf.json').write_text(paper.model_dump_json(indent=2),encoding='utf-8')
    (destination/'viewer-template.html').write_text(html.replace(safe_json(paper),'__IPDF_PAYLOAD__'),encoding='utf-8')
    (destination/'.nojekyll').write_text('',encoding='utf-8')
    print('Built static viewer and authored demo in docs/ (no API calls).')

if __name__=='__main__':
    build()
