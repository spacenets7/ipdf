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
    paper=IPDF.model_validate(dict(
        meta=dict(title='Welcome to iPDF',authors=['iPDF'],source_url='https://github.com/blackfang007/ipdf/blob/main/SPEC.md',level='beginner'),
        sections=[dict(id='welcome',title='A paper with more ways in',page=1,text=
            'iPDF keeps the original paper at the center. Open an exported iPDF JSON file to explore its source sections, glossary, flashcards, charts and narration. This welcome document is an authored format demonstration, not generated research output.\n\nCreate annotated papers with the FastAPI application. The GitHub Pages edition reads existing files locally in your browser and never calls a language model.')],
        provenance=dict(model='authored demonstration',prompt_versions={},generated_at='2026-10-23T00:00:00Z')))
    html=export_html(paper)
    (destination/'demo.html').write_text(html,encoding='utf-8')
    (destination/'viewer-template.html').write_text(html.replace(safe_json(paper),'__IPDF_PAYLOAD__'),encoding='utf-8')
    (destination/'.nojekyll').write_text('',encoding='utf-8')
    print('Built static viewer and authored demo in docs/ (no API calls).')

if __name__=='__main__':
    build()
