import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime,timedelta,timezone
from app.modules.digest.sources.rss import RSSSource
from app import db

if __name__=='__main__':
    db.init_db()
    url=sys.argv[1] if len(sys.argv)>1 else 'https://feeds.bbci.co.uk/news/science_and_environment/rss.xml'
    items=RSSSource(url,max_items=1).fetch([],datetime.now(timezone.utc)-timedelta(days=7))
    for item in items:
        row=db.upsert_item(item)
        print(f'RSS article {row["id"]}: {item.title}\n{item.url}\nExtracted {len(item.raw_text)} characters\n{item.raw_text[:500]}')
    if not items:
        raise SystemExit('No usable article returned')
