import logging
import re
from datetime import datetime, timezone
import feedparser
import httpx
from app.modules.digest.sources.base import Item
from app.config import settings

log = logging.getLogger(__name__)
TOPICS = {'artificial intelligence':'cs.AI','machine learning':'cs.LG','quantum physics':'quant-ph',
          'computer vision':'cs.CV','natural language processing':'cs.CL','robotics':'cs.RO',
          'statistics':'stat.ML','physics':'physics','cs.ai':'cs.AI','cs.lg':'cs.LG',
          'cs.cv':'cs.CV','cs.cl':'cs.CL','cs.ro':'cs.RO','quant-ph':'quant-ph'}


def topic_query(topics):
    terms = []
    for topic in topics[:12]:
        clean = re.sub(r'[^\w .-]', ' ', topic).strip()[:80]
        category = TOPICS.get(clean.lower())
        if not category and re.fullmatch(r'[a-z-]+\.[A-Z]{2}',clean):
            category = clean
        if clean:
            terms.append('cat:'+category if category else f'all:"{clean}"')
    return '(' + ' OR '.join(terms or ['cat:cs.AI']) + ')'


def parse_feed(content):
    feed = feedparser.parse(content)
    items = []
    for entry in feed.entries:
        if 'api/errors' in entry.get('id',''):
            raise ValueError('arXiv rejected the query')
        url = entry.get('id','').replace('http://','https://')
        if not url.startswith('https://arxiv.org/abs/'):
            continue
        paper_id = url.rsplit('/',1)[-1]
        items.append(Item(source='arxiv',external_id='arxiv:'+paper_id,
            title=' '.join(entry.title.split()),authors=[a.name for a in entry.get('authors',[])],
            url=url,published=entry.get('published',''),raw_text='Abstract\n'+' '.join(entry.get('summary','').split()),
            tags=[t.term for t in entry.get('tags',[])],pdf_url='https://arxiv.org/pdf/'+paper_id))
    return items


class ArxivSource:
    def fetch(self, topics, since: datetime):
        if settings.offline:
            return []
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        query = topic_query(topics) + f' AND submittedDate:[{since.strftime("%Y%m%d%H%M")} TO 300001010000]'
        with httpx.Client(timeout=30,follow_redirects=True,headers={'User-Agent':'LazyDigest/1.0 (local research reader)'}) as client:
            response = client.get('https://export.arxiv.org/api/query',params={
                'search_query':query,'start':0,'max_results':settings.max_items,
                'sortBy':'submittedDate','sortOrder':'descending'})
            response.raise_for_status()
        return parse_feed(response.content)[:settings.max_items]
