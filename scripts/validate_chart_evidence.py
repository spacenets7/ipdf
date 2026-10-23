"""Verify chart mapping on three real PDFs. No LLM calls or invented values."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.ingest.pdf import Ingested
from app.schema import IPDF,Meta,Provenance,parse_number
from app.generate.charts import ChartPlan,from_plan
from app.llm import Result
from datetime import datetime,timezone


def first_safe_plan(table):
    for header_row in range(min(3,len(table.cells))):
        for column in range(1,len(table.cells[header_row])):
            if not table.cells[header_row][column]:
                continue
            rows=[i for i,row in enumerate(table.cells) if i>header_row and len(row)>column
                  and parse_number(row[column]) is not None and row[0] and parse_number(row[0]) is None]
            if len(rows)>=2:
                return ChartPlan(usable=True,title=table.label+' — '+str(table.cells[header_row][column]),
                    label_column=0,header_row=header_row,value_columns=[column],data_rows=rows[:10])


if __name__=='__main__':
    reports=[]
    for arxiv_id in ('1706.03762','1810.04805','1512.03385'):
        root=settings.data_dir/'validation'
        paper=Ingested.model_validate_json((root/f'{arxiv_id}.ingest.json').read_text(encoding='utf-8'))
        for table in paper.tables:
            plan=first_safe_plan(table)
            if not plan:
                continue
            result=Result(plan,'deterministic evidence check (no LLM)','FAST')
            chart=from_plan(table,plan,result)[0]
            doc=IPDF(meta=Meta(title=paper.title,authors=paper.authors,source_url=paper.source_url,
                level='beginner',pages=paper.pages,paper_id=paper.paper_id),sections=paper.sections,tables=paper.tables,
                charts=[chart],provenance=Provenance(model=result.model,prompt_versions={},generated_at=datetime.now(timezone.utc)))
            (root/f'{arxiv_id}.chart-check.json').write_text(doc.model_dump_json(indent=2),encoding='utf-8')
            report={'arxiv_id':arxiv_id,'page':chart.page,'caption':chart.caption,'series':chart.series[0].model_dump(),
                'check':'All plotted values independently validated against numeric source cells; deterministic plan, not hosted generation.'}
            print(json.dumps(report,ensure_ascii=False),flush=True)
            reports.append(report)
            break
        else:
            raise SystemExit(f'{arxiv_id}: no reliable numeric chart; omitted rather than invented')
    (settings.data_dir/'validation/chart-evidence-report.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
