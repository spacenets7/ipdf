import re
import httpx
import feedparser


def normalize_id(value):
    value=value.strip()
    value=re.sub(r'^https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/','',value).removesuffix('.pdf')
    if not re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?',value):
        raise ValueError('Enter an arXiv ID such as 1706.03762 or its arxiv.org URL.')
    return value


def fetch_pdf(value):
    paper_id=normalize_id(value)
    url='https://arxiv.org/pdf/'+paper_id
    metadata={'title':'','authors':[],'source_url':url}
    with httpx.Client(timeout=httpx.Timeout(45,connect=10),follow_redirects=True,headers={'User-Agent':'iPDF/0.1 (interactive research reader)'}) as client:
        try:
            response=client.get('https://export.arxiv.org/api/query',params={'id_list':paper_id})
            response.raise_for_status()
            feed=feedparser.parse(response.content)
            if feed.entries:
                metadata['title']=' '.join(feed.entries[0].get('title','').split())
                metadata['authors']=[a.name for a in feed.entries[0].get('authors',[])]
        except Exception:
            pass  # PDF title remains available when Atom metadata is unavailable.
        last=None
        for host in ('arxiv.org','export.arxiv.org','arxiv.org'):
            try:
                with client.stream('GET','https://'+host+'/pdf/'+paper_id) as response:
                    response.raise_for_status()
                    data=bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data)>25_000_000:
                            raise ValueError('PDF exceeds the 25 MB upload limit.')
                if not data.startswith(b'%PDF'):
                    raise ValueError('arXiv did not return a PDF')
                break
            except httpx.HTTPError as exc:
                last=exc
        else:
            raise ValueError('arXiv PDF is temporarily unavailable. Try uploading a downloaded PDF.') from last
    if not data.startswith(b'%PDF'):
        raise ValueError('arXiv did not return a PDF. Try uploading the file instead.')
    return bytes(data),metadata
