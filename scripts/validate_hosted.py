"""Real hosted plugins for one paper at all three levels. Never uses local inference."""
import argparse
import json
import sys
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import db
from app.config import settings
from app.extract import extract_document
from app.generate.pipeline import build
from app.llm import run_id

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--pdf',type=Path,default=Path('data/validation/1706.03762.pdf'))
    parser.add_argument('--max-sections',type=int,help='Optional explicit smoke-test limit; report states it')
    args=parser.parse_args()
    chosen=settings.backend()
    if not chosen.api_key or not chosen.model:
        raise SystemExit('Hosted generation not run: set LLM_API_KEY and LLM_MODEL in .env first.')
    db.init_db()
    if args.max_sections:
        settings.generation_sections=max(1,args.max_sections)
    paper=extract_document(args.pdf.read_bytes())
    root=settings.data_dir/'validation'
    root.mkdir(parents=True,exist_ok=True)
    for level in ('beginner','intermediate','expert'):
        token=run_id.set('validation-'+level+'-'+uuid.uuid4().hex)
        try:
            result=build(paper,level,lambda percent,message:print(level,percent,message,flush=True))
            output=root/f'hosted-{level}.ipdf.json'
            output.write_text(result.model_dump_json(indent=2),encoding='utf-8')
            print(json.dumps({'level':level,'model':chosen.model,'section_limit':settings.generation_sections,
                'glossary':[v.model_dump() for v in result.glossary[:2]],
                'flashcards':[v.model_dump() for v in result.flashcards[:2]],
                'narration':[v.model_dump() for v in result.narration[:1]],
                'cost':result.provenance.recorded_cost_usd,'issues':len(result.issues)},ensure_ascii=False),flush=True)
        finally:
            run_id.reset(token)
