"""Explicitly mocked UI fixture. Never presented as hosted generation evidence."""
import sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import db
from app.config import settings
from app.schema import IPDF,Glossary,Flashcard,Narration,GeneratedBy

if __name__=='__main__':
    db.init_db()
    root=settings.data_dir/'validation'
    document=IPDF.model_validate_json((root/'1706.03762.chart-check.json').read_text(encoding='utf-8'))
    chart=document.charts[0]
    section=next(s for s in document.sections if s.page==chart.page)
    section.text='Transformer (4 layers) appears in the source table on this page. '+section.text[:1100]
    document.sections=[section]
    document.meta.title='Interactive paper · Mocked UI test fixture'
    document.meta.source_url=f'/media/papers/{document.meta.paper_id}.pdf'
    def by(plugin):
        return GeneratedBy(plugin=plugin,prompt_version='ui-fixture/0.1',model='MOCKED UI FIXTURE — no hosted generation',source_page=section.page)
    document.glossary=[Glossary(term='Transformer',definition='The model named in the comparison on this source page. This definition is a mocked UI test fixture.',
        section_id=section.id,page=section.page,generated_by=by('glossary'))]
    document.flashcards=[Flashcard(id='fixture-card',front='Where can the chart values be checked?',
        back='In Table 4 on page 10 of the source PDF. This card is a mocked UI fixture.',section_id=section.id,page=section.page,generated_by=by('flashcards'))]
    document.narration=[Narration(section_id=section.id,page=section.page,
        script='You are listening to a mocked interface test. The chart uses values from Table four on page ten. This is the end of this test section.',
        simpler_script='This is a simpler replay for the interface test. Each bar comes from a number in the source table. End of the test.',generated_by=by('narration'))]
    document.provenance.model='MOCKED UI FIXTURE — no hosted generation'
    document.provenance.prompt_versions={'ui_fixture':'ui-fixture/0.1'}
    document=IPDF.model_validate(document.model_dump())
    db.execute('''INSERT INTO ipdfs(id,paper_id,level,model,cache_key,json) VALUES(?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET json=excluded.json''',
        ('ui-test-fixture',document.meta.paper_id,'beginner',document.provenance.model,'ui-test-fixture',document.model_dump_json()))
    print('Mocked UI fixture: http://127.0.0.1:8000/ipdf/ui-test-fixture')
