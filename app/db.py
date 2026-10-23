"""Short-lived SQLite connections: safe across the summarization worker pool."""
import json
import sqlite3
from contextlib import contextmanager

from app.config import settings

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, level TEXT NOT NULL,
 topics_json TEXT NOT NULL, topic_weights_json TEXT NOT NULL,
 level_offset REAL NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS items (
 id INTEGER PRIMARY KEY, source TEXT NOT NULL, external_id TEXT UNIQUE NOT NULL,
 title TEXT NOT NULL, authors TEXT NOT NULL, url TEXT NOT NULL, published TEXT NOT NULL,
 raw_text TEXT NOT NULL, fetched_at TEXT DEFAULT CURRENT_TIMESTAMP, tags_json TEXT DEFAULT '[]', pdf_url TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS summaries (
 id INTEGER PRIMARY KEY, item_id INTEGER REFERENCES items(id), level TEXT, model TEXT,
 json TEXT, prompt_tokens INTEGER, completion_tokens INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(item_id,level,model));
CREATE TABLE IF NOT EXISTS analyses (
 id INTEGER PRIMARY KEY, item_id INTEGER REFERENCES items(id), level TEXT, model TEXT,
 json TEXT, prompt_tokens INTEGER, completion_tokens INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(item_id,level,model));
CREATE TABLE IF NOT EXISTS digests (
 id INTEGER PRIMARY KEY, user_id TEXT REFERENCES users(id), date TEXT, markdown TEXT,
 payload_json TEXT NOT NULL DEFAULT '[]', profile_key TEXT NOT NULL DEFAULT '', warnings_json TEXT DEFAULT '[]',
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS digest_lookup ON digests(user_id,date,id);
CREATE TABLE IF NOT EXISTS feedback (
 id INTEGER PRIMARY KEY, user_id TEXT REFERENCES users(id), item_id INTEGER REFERENCES items(id),
 signal TEXT CHECK(signal IN ('up','down','too_hard','too_easy')), created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audio (
 id INTEGER PRIMARY KEY, item_id INTEGER REFERENCES items(id), digest_id INTEGER REFERENCES digests(id),
 level TEXT, provider TEXT, voice TEXT, text_hash TEXT UNIQUE, path TEXT, chars INTEGER,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS narrations (
 input_hash TEXT PRIMARY KEY, script TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audio_access (
 user_id TEXT REFERENCES users(id), text_hash TEXT REFERENCES audio(text_hash), PRIMARY KEY(user_id,text_hash));
CREATE TABLE IF NOT EXISTS usage (
 id INTEGER PRIMARY KEY, kind TEXT, backend TEXT, model TEXT, purpose TEXT,
 prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0,
 chars INTEGER DEFAULT 0, cost REAL DEFAULT 0, latency REAL DEFAULT 0,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS papers (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, source_url TEXT NOT NULL,
 pdf_path TEXT NOT NULL, ingest_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS ipdfs (
 id TEXT PRIMARY KEY, paper_id TEXT REFERENCES papers(id), level TEXT NOT NULL,
 model TEXT NOT NULL, cache_key TEXT UNIQUE NOT NULL, json TEXT NOT NULL,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL, progress INTEGER DEFAULT 0,
 message TEXT DEFAULT '', result_id TEXT, result_json TEXT, error TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS plugin_cache (
 cache_key TEXT PRIMARY KEY, json TEXT NOT NULL, model TEXT NOT NULL, backend TEXT NOT NULL,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);
'''


@contextmanager
def connection():
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=30000')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with connection() as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.executescript(SCHEMA)
        columns={row['name'] for row in conn.execute('PRAGMA table_info(usage)')}
        if 'run_id' not in columns:
            conn.execute('ALTER TABLE usage ADD COLUMN run_id TEXT')


def query(sql, args=(), one=False):
    with connection() as conn:
        rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    with connection() as conn:
        return conn.execute(sql, args).lastrowid


def get_user(user_id):
    row = query('SELECT * FROM users WHERE id=?', (user_id,), one=True) if user_id else None
    if row:
        row['topics'] = json.loads(row['topics_json'])
        row['topic_weights'] = json.loads(row['topic_weights_json'])
    return row


def upsert_item(item):
    execute('''INSERT INTO items(source,external_id,title,authors,url,published,raw_text,tags_json,pdf_url)
        VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(external_id) DO UPDATE SET
        title=excluded.title,authors=excluded.authors,tags_json=excluded.tags_json,
        raw_text=CASE WHEN length(excluded.raw_text)>length(items.raw_text) THEN excluded.raw_text ELSE items.raw_text END,
        fetched_at=CURRENT_TIMESTAMP''',
        (item.source,item.external_id,item.title,json.dumps(item.authors),item.url,item.published,
         item.raw_text,json.dumps(item.tags),item.pdf_url))
    return query('SELECT * FROM items WHERE external_id=?', (item.external_id,), one=True)


def cache_get(table, item_id, level, model):
    assert table in ('summaries', 'analyses')
    return query(f'SELECT * FROM {table} WHERE item_id=? AND level=? AND model=?', (item_id,level,model), one=True)


def cache_put(table, item_id, level, result):
    assert table in ('summaries', 'analyses')
    execute(f'''INSERT INTO {table}(item_id,level,model,json,prompt_tokens,completion_tokens) VALUES(?,?,?,?,?,?)
        ON CONFLICT(item_id,level,model) DO UPDATE SET json=excluded.json,
        prompt_tokens=excluded.prompt_tokens,completion_tokens=excluded.completion_tokens''',
        (item_id,level,result.model,result.value.model_dump_json(),result.prompt_tokens,result.completion_tokens))
