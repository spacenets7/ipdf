import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import db
from app.modules.digest.levels import LEVELS
from app.modules.digest.summarize import summarize

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--deep',action='store_true')
    args=parser.parse_args()
    db.init_db()
    items=db.query('SELECT * FROM items ORDER BY published DESC LIMIT 3')
    if not items:
        raise SystemExit('No papers cached. Run scripts/validate_sources.py first.')
    if args.deep:
        from app.modules.digest.deep import analyze
        for item in items[:2]:
            result=analyze(item,'intermediate')
            print(json.dumps({'paper':item['title'],'backend':result.backend,'model':result.model,
                              'analysis':result.value.model_dump()},ensure_ascii=False),flush=True)
    else:
        for item in items:
            for level in LEVELS:
                result=summarize(item,level)
                print(json.dumps({'paper':item['title'],'level':level,'model':result.model,
                                  'summary':result.value.model_dump()},ensure_ascii=False),flush=True)
