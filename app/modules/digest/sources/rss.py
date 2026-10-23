import ipaddress
import logging
import socket
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin,urlsplit

import feedparser
import httpx
import trafilatura

from app.config import settings
from app.modules.digest.sources.base import Item

log=logging.getLogger(__name__)


def public_url(url):
    parsed=urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Feed and article links must be public HTTP(S) URLs')
    addresses=socket.getaddrinfo(parsed.hostname,parsed.port or (443 if parsed.scheme=='https' else 80),type=socket.SOCK_STREAM)
    if any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise ValueError('Private network feed and article links are not allowed')
    return url


def download(url):
    with httpx.Client(timeout=20,headers={'User-Agent':'LazyDigest/1.0 research reader'}) as client:
        for _ in range(5):
            public_url(url)
            with client.stream('GET',url) as response:
                if response.is_redirect:
                    url=urljoin(url,response.headers['location'])
                    continue
                response.raise_for_status()
                data=bytearray()
                for part in response.iter_bytes():
                    data.extend(part)
                    if len(data)>5_000_000:
                        raise ValueError('Feed or article exceeds 5 MB')
                return bytes(data)
    raise ValueError('Too many feed redirects')


class RSSSource:
    def __init__(self,url,max_items=None):
        self.url=url
        self.max_items=max_items or settings.max_items

    def fetch(self,topics,since):
        if settings.offline:
            return []
        feed=feedparser.parse(download(self.url))
        if feed.bozo and not feed.entries:
            raise ValueError('Feed could not be parsed')
        items=[]
        for entry in feed.entries:
            if len(items)>=self.max_items:
                break
            try:
                parsed=entry.get('published_parsed') or entry.get('updated_parsed')
                date=datetime(*parsed[:6],tzinfo=timezone.utc) if parsed else datetime.now(timezone.utc)
                if since.tzinfo is None:
                    since=since.replace(tzinfo=timezone.utc)
                if date<since:
                    continue
                link=public_url(entry.link)
                html=download(link)
                text=trafilatura.extract(html,include_comments=False,include_tables=False)
                if not text or len(text)<100:
                    text=trafilatura.extract(entry.get('summary','')) or entry.get('summary','')
                if not text or len(text)<100:
                    continue
                items.append(Item(source='rss',external_id='rss:'+link,title=entry.title,
                    authors=[entry.author] if entry.get('author') else [],url=link,published=date.isoformat(),
                    raw_text=text[:200_000],tags=[tag.term for tag in entry.get('tags',[])]))
            except Exception as exc:
                log.warning('Skipping news article (%s)',type(exc).__name__)
        return items
