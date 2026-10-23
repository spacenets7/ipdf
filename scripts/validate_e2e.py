"""HTTP end-to-end checks on three real PDFs. Reports source-only honestly."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from app.schema import IPDF
from app.config import settings

if __name__=='__main__':
    base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8000'
    reports=[]
    with httpx.Client(base_url=base,timeout=30) as client:
        configured=client.get('/health').json()['llm_configured']
        print('Integration mode:', 'HOSTED GENERATION' if configured else 'SOURCE-ONLY (hosted credentials missing)',flush=True)
        for arxiv_id,level in zip(('1706.03762','1810.04805','1512.03385'),('beginner','intermediate','expert')):
            path=settings.data_dir/'validation'/f'{arxiv_id}.pdf'
            before=time.monotonic()
            response=client.post('/ipdf/create',files={'pdf':(path.name,path.read_bytes(),'application/pdf')},data={'level':level})
            response.raise_for_status()
            request_seconds=time.monotonic()-before
            job=response.json()['job_id']
            while True:
                state=client.get('/ipdf/status/'+job).json()
                if state['state'] in ('ready','error'):
                    break
                time.sleep(1)
            if state['state']!='ready':
                raise SystemExit(state)
            identifier=state['result_id']
            raw=client.get(f'/ipdf/{identifier}.json')
            raw.raise_for_status()
            paper=IPDF.model_validate(raw.json())
            viewer=client.get(f'/ipdf/{identifier}')
            viewer.raise_for_status()
            exported=client.get(f'/ipdf/{identifier}/export')
            exported.raise_for_status()
            (settings.data_dir/'validation'/f'{arxiv_id}.ipdf.html').write_text(exported.text,encoding='utf-8')
            (settings.data_dir/'validation'/f'{arxiv_id}.ipdf.json').write_text(raw.text,encoding='utf-8')
            report={'arxiv_id':arxiv_id,'level':level,'viewer':base+f'/ipdf/{identifier}',
                'create_response_seconds':round(request_seconds,3),'total_seconds':round(time.monotonic()-before,2),
                'sections':len(paper.sections),'glossary':len(paper.glossary),'flashcards':len(paper.flashcards),
                'charts':len(paper.charts),'narration':len(paper.narration),'issues':len(paper.issues),
                'model':paper.provenance.model,'recorded_cost_usd':paper.provenance.recorded_cost_usd,
                'source_only':not bool(paper.glossary or paper.flashcards or paper.narration)}
            reports.append(report)
            print(json.dumps(report),flush=True)
    (settings.data_dir/'validation/e2e-report.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
