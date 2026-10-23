"""Real, uncached generation on the same papers; never fabricate hosted costs."""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from app import db
from app.config import settings
from app.modules.digest.judge import judge
from app.modules.digest.summarize import summarize


def main():
    parser=argparse.ArgumentParser(description='FAST vs DEEP on identical cached source text')
    parser.add_argument('--limit',type=int,default=20)
    parser.add_argument('--level',choices=['beginner','intermediate','expert'],default='intermediate')
    parser.add_argument('--output',type=Path,default=Path('data/benchmark.md'))
    args=parser.parse_args()
    db.init_db()
    papers=db.query('SELECT * FROM items ORDER BY published DESC LIMIT ?',(max(1,min(20,args.limit)),))
    if not papers:
        raise SystemExit('No cached papers. Run scripts/validate_sources.py first.')
    if len(papers)<args.limit:
        print(f'Only {len(papers)} papers cached; the report will state the actual sample size.',flush=True)
    start_id=db.query('SELECT COALESCE(MAX(id),0) AS n FROM usage',one=True)['n']
    rows=[]
    for backend in ('FAST','DEEP'):
        for paper in papers:
            before=time.monotonic()
            try:
                result=summarize(paper,args.level,force=True,backend=backend)
                summary_seconds=time.monotonic()-before
                verdict=judge(paper,result.value)
                rows.append({'requested':backend,'actual':result.backend,'title':paper['title'],
                    'latency':summary_seconds,'in':result.prompt_tokens,'out':result.completion_tokens,
                    'cost':result.cost,'passed':verdict.passed,'summary':result.value.tldr})
                print(f'{backend} ({result.backend}): {paper["title"][:65]} — {summary_seconds:.1f}s, judge={verdict.passed}',flush=True)
            except Exception as exc:
                rows.append({'requested':backend,'title':paper['title'],'error':str(exc)})
                print(f'{backend}: failed ({type(exc).__name__})',flush=True)
    calls=db.query('SELECT * FROM usage WHERE id>?',(start_id,))
    lines=['# LazyDigest — FAST vs DEEP benchmark',f'Sample: {len(papers)} identical papers; level: {args.level}.',
           'Each summary is freshly generated. Latency/tokens in the table cover summary calls (including validation retries). '
           'The run total also includes judge calls. API token prices are USD per million tokens.','']
    if settings.backend('DEEP').name=='FAST':
        lines+=['**DEEP credentials were not configured: both columns use FAST. This is a local fallback comparison, not an Ultramarine benchmark.**','']
    lines+=['| Requested backend (actual model) | Completed | Mean latency | Prompt tokens | Completion tokens | Summary $ | Judge pass rate |',
            '|---|---:|---:|---:|---:|---:|---:|']
    for backend in ('FAST','DEEP'):
        group=[r for r in rows if r['requested']==backend and 'error' not in r]
        chosen=settings.backend(backend)
        priced=chosen.name=='FAST' or chosen.price_in>0 or chosen.price_out>0
        money=f'${sum(r["cost"] for r in group):.6f}' if priced else 'unpriced'
        lines.append(f'| {backend} ({chosen.model}) | {len(group)}/{len(papers)} | '+
            (f'{statistics.mean(r["latency"] for r in group):.2f}s' if group else 'failed')+
            f' | {sum(r["in"] for r in group)} | {sum(r["out"] for r in group)} | {money} | '+
            (f'{sum(r["passed"] for r in group)/len(group):.0%}' if group else 'n/a')+' |')
    total=sum(c['cost'] for c in calls)
    unpriced=any(c['backend']=='DEEP' and settings.backend('DEEP').price_in==0 and settings.backend('DEEP').price_out==0 for c in calls)
    lines+=['',f'Total recorded run cost (all {len(calls)} LLM calls, including judges): **${total:.6f}**.',
            f'Total tokens: {sum(c["prompt_tokens"] for c in calls)} prompt / {sum(c["completion_tokens"] for c in calls)} completion.',
            'Local inference has no API charge; electricity and hardware costs are not measured.']
    if unpriced:
        lines+=['**Hosted prices were unset. Recorded dollars are incomplete; set DEEP_PRICE_IN/DEEP_PRICE_OUT before claiming an actual hosted cost.**']
    lines+=['','## Three side-by-side summaries','| Paper | FAST | DEEP |','|---|---|---|']
    for paper in papers[:3]:
        values=[]
        for backend in ('FAST','DEEP'):
            found=next(r for r in rows if r['requested']==backend and r['title']==paper['title'])
            values.append(found.get('summary',found.get('error','Failed')).replace('|','\\|').replace('\n',' '))
        lines.append('| '+paper['title'].replace('|','\\|')+' | '+' | '.join(values)+' |')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    report='\n'.join(lines)+'\n'
    args.output.write_text(report,encoding='utf-8')
    print(report)
    print('Saved',args.output.resolve())
    if any('error' in row for row in rows):
        raise SystemExit(1)


if __name__=='__main__':
    main()
