import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.extract import extract_document
from app.ingest.arxiv import fetch_pdf
from app.config import settings

PAPERS=['1706.03762','1810.04805','1512.03385']

if __name__=='__main__':
    root=settings.data_dir/'validation'
    root.mkdir(parents=True,exist_ok=True)
    reports=[]
    for arxiv_id in PAPERS:
        path=root/f'{arxiv_id}.pdf'
        metadata={'source_url':'https://arxiv.org/pdf/'+arxiv_id}
        if not path.exists():
            content,metadata=fetch_pdf(arxiv_id)
            path.write_bytes(content)
        paper=extract_document(path.read_bytes(),metadata)
        (root/f'{arxiv_id}.ingest.json').write_text(paper.model_dump_json(indent=2),encoding='utf-8')
        report={'arxiv_id':arxiv_id,'title':paper.title,'pages':paper.pages,'sections':len(paper.sections),
            'tables':len(paper.tables),'figures':len(paper.figures),
            'table_samples':[{'label':t.label,'page':t.page,'rows':len(t.cells),'cells':t.cells[:3]} for t in paper.tables[:3]]}
        reports.append(report)
        print(json.dumps(report,ensure_ascii=False),flush=True)
    (root/'ingestion-report.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
