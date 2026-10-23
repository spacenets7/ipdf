import hashlib
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app import db
from app.config import settings
from app.extract import enrich
from app.modules.digest.judge import verified_summary
from app.modules.digest.levels import effective_level
from app.llm import LLMError
from app.modules.digest.rank import rank, topic_matches
from app.modules.digest.sources.arxiv import ArxivSource

log = logging.getLogger(__name__)
_build_lock = threading.Lock()


def today():
    return datetime.now(ZoneInfo(settings.timezone)).date().isoformat()


def profile_key(user):
    profile = [user['level'],user['level_offset'],user['topics'],user['topic_weights'],
               settings.backend('FAST').model,settings.backend('DEEP').model,settings.deep_top_k]
    return hashlib.sha256(json.dumps(profile,sort_keys=True).encode()).hexdigest()


def load_digest(row):
    if not row:
        return None
    return {**row,'rows':json.loads(row['payload_json']),'warnings':json.loads(row['warnings_json'])}


def latest_digest(user_id):
    return load_digest(db.query('SELECT * FROM digests WHERE user_id=? ORDER BY id DESC LIMIT 1',(user_id,),one=True))


def markdown_digest(user, rows, warnings, level):
    lines = [f'# LazyDigest — {today()}',f'For {user["name"]} · {level} · {len(rows)} papers','']
    lines.extend('> '+warning for warning in warnings)
    for row in rows:
        item,s = row['item'],row['summary']
        lines += ['',f'## {item["title"]}',f'Source: {item["url"]}',
                  f'Published: {item["published"]} · Model: {row["model"]} · '
                  + ('Grounding check passed' if row['verified'] else 'UNVERIFIED'),'',s['tldr'],'']
        lines.extend('- '+p for p in s['key_points'])
        lines += ['',f'**Why it matters:** {s["why_it_matters"]}',f'**Limitations:** {s["limitations"]}']
        if s['prerequisites']:
            lines.append('**Prerequisites:** '+', '.join(s['prerequisites']))
        if not row['verified']:
            lines.append('**Verification concerns:** '+'; '.join(row['verification_reasons']))
        if row.get('analysis'):
            lines += ['','### Deep analysis',f'Model: {row["analysis_model"]}']
            for key,value in row['analysis'].items():
                lines += ['',f'**{key.replace("_"," ").title()}**']
                lines.extend(['- '+str(v) for v in value] if isinstance(value,list) else [str(value)])
    lines += ['','---','Generated from the linked source text. Grounding checks are model judgments; read the original before relying on a claim.','']
    return '\n'.join(lines)


def _process(item,level):
    item['raw_text'] = enrich(item)
    result,verdict = verified_summary(item,level)
    return {'item':item,'summary':result.value.model_dump(),'model':result.model,
            'verified':verdict.passed,'verification_reasons':verdict.reasons,'level':level}


def build_digest(user, *, refresh=False):
    # Serial builds avoid duplicate daily work; FAST within a build uses a pool.
    with _build_lock:
        key = profile_key(user)
        cached = db.query('SELECT * FROM digests WHERE user_id=? AND date=? AND profile_key=? ORDER BY id DESC LIMIT 1',
                          (user['id'],today(),key),one=True)
        if cached and not refresh:
            return load_digest(cached)
        warnings = []
        fresh_ids = []
        if not settings.offline:
            try:
                fresh = ArxivSource().fetch(user['topics'],datetime.now(timezone.utc)-timedelta(days=3))
                if settings.rss_feed:
                    from app.modules.digest.sources.rss import RSSSource
                    try:
                        fresh += RSSSource(settings.rss_feed).fetch(user['topics'],datetime.now(timezone.utc)-timedelta(days=3))
                    except Exception:
                        warnings.append('The news feed is unavailable; continuing with papers.')
                fresh_ids = [db.upsert_item(item)['id'] for item in fresh]
            except Exception as exc:
                log.warning('Source fetch failed (%s)',type(exc).__name__)
                warnings.append('Paper source unavailable. Using matching papers already saved on this device.')
        else:
            warnings.append('Offline mode: using papers saved on this device.')
        if fresh_ids:
            candidates = db.query('SELECT * FROM items WHERE id IN ('+','.join('?'*len(fresh_ids))+') ORDER BY published DESC',fresh_ids)
        else:
            candidates = db.query('SELECT * FROM items ORDER BY published DESC LIMIT 200')
            candidates = [i for i in candidates if any(topic_matches(t,i['title']+' '+i['raw_text'],json.loads(i['tags_json'])) for t in user['topics'])]
            if candidates and not warnings:
                warnings.append('No new matching papers in the last three days. Showing saved papers, with their original dates.')
        candidates = candidates[:settings.max_items]
        level = effective_level(user)
        rows = []
        if candidates:
            with ThreadPoolExecutor(max_workers=settings.fast_workers) as pool:
                futures = {pool.submit(_process,item,level):item for item in candidates}
                for future in as_completed(futures):
                    try:
                        rows.append(future.result())
                    except Exception as exc:
                        log.warning('Skipping paper %s (%s)',futures[future]['id'],type(exc).__name__)
            if not rows:
                raise LLMError('Papers are saved, but local summarization failed. Start Ollama and check the configured model.')
            if len(rows) < len(candidates):
                warnings.append(f'{len(candidates)-len(rows)} papers could not be summarized and were skipped.')
        seen = set()
        for old in db.query('SELECT payload_json FROM digests WHERE user_id=?',(user['id'],)):
            seen.update(r['item']['id'] for r in json.loads(old['payload_json']))
        rows = rank(rows,user,level,seen)
        from app.modules.digest.deep import analyze
        for row in rows[:settings.deep_top_k]:
            try:
                result = analyze(row['item'],level)
                row['analysis'] = result.value.model_dump()
                row['analysis_model'] = result.model
            except Exception as exc:
                log.warning('Deep analysis failed (%s)',type(exc).__name__)
                row['analysis_error'] = 'Deep analysis is temporarily unavailable. The summary is still available.'
        if not rows:
            warnings.append('No matching papers are saved yet. Connect to arXiv or choose another topic.')
        markdown = markdown_digest(user,rows,warnings,level)
        digest_id = db.execute('''INSERT INTO digests(user_id,date,markdown,payload_json,profile_key,warnings_json)
            VALUES(?,?,?,?,?,?)''',(user['id'],today(),markdown,json.dumps(rows),key,json.dumps(warnings)))
        return load_digest(db.query('SELECT * FROM digests WHERE id=?',(digest_id,),one=True))
