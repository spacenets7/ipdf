"""Live source probe; no test fixtures or invented results."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime,timedelta,timezone
from app import db
from app.modules.digest.sources.arxiv import ArxivSource

if __name__ == '__main__':
    db.init_db()
    papers = ArxivSource().fetch(['cs.AI','cs.LG'],datetime.now(timezone.utc)-timedelta(days=3))
    print(f'arXiv returned {len(papers)} papers from the last 3 days')
    for paper in papers:
        row = db.upsert_item(paper)
        if papers.index(paper) < 3:
            print(row['id'],paper.title,paper.url,paper.raw_text[:240],sep='\n')
