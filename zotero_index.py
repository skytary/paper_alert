"""Zotero 라이브러리의 DOI·제목 목록을 로컬 DB에 두고 갱신한다 (이미 있는 논문 확인용).

Zotero Web API의 DOI 검색은 큰 라이브러리에서 너무 느리므로, 최상위 항목의 DOI와 정규화 제목을
한 번 내려받아 두고 이후에는 라이브러리 버전(since)으로 바뀐 항목·지운 항목만 받아 갱신한다.
"""
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

import database
import zotero_client

TIMEOUT = 60
PAGE = 100                    # 처음 만들 때 한 번에 받는 항목 수
WORKERS = 4                   # 처음 만들 때 동시에 보내는 요청 수
STALE_SECONDS = 300           # 마지막 갱신 후 이 시간이 지나야 보내기 전에 다시 갱신
SKIP_TYPES = {'attachment', 'note', 'annotation'}
DOI_RE = re.compile(r'\b(10\.\d{4,9}/[^\s<>"\'?#&]+)', re.IGNORECASE)

_lock = threading.Lock()
status = {'running': False, 'done': 0, 'total': 0, 'error': None}


def init_tables():
    with database.get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS zotero_index (
                key TEXT PRIMARY KEY,
                doi TEXT,
                title_norm TEXT,
                item_type TEXT
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS zi_doi ON zotero_index(doi)')
        conn.execute('CREATE INDEX IF NOT EXISTS zi_title ON zotero_index(title_norm)')
        conn.execute('CREATE TABLE IF NOT EXISTS zotero_meta (key TEXT PRIMARY KEY, value TEXT)')
        conn.commit()


def _meta(key: str, default: str = '') -> str:
    with database.get_connection() as conn:
        row = conn.execute('SELECT value FROM zotero_meta WHERE key = ?', (key,)).fetchone()
    return row[0] if row else default


def _set_meta(**values):
    with database.get_connection() as conn:
        for k, v in values.items():
            conn.execute('INSERT OR REPLACE INTO zotero_meta (key, value) VALUES (?, ?)', (k, str(v)))
        conn.commit()


def info() -> dict:
    with database.get_connection() as conn:
        count = conn.execute('SELECT COUNT(*) FROM zotero_index').fetchone()[0]
    return {'items': count, 'version': int(_meta('version', '0')),
            'last_sync': _meta('last_sync'), **status}


def _doi_of(data: dict) -> str | None:
    for text in (data.get('DOI'), data.get('extra'), data.get('url')):
        m = DOI_RE.search(text or '')
        if m:
            return m.group(1).rstrip('.,;)').lower()
    return None


def _row(item: dict) -> tuple | None:
    data = item['data']
    if data.get('itemType') in SKIP_TYPES:
        return None
    return (data['key'], _doi_of(data), database.norm_title(data.get('title')), data.get('itemType'))


def _get(url: str, headers: dict, params: dict) -> requests.Response:
    for attempt in range(4):
        r = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
        if r.status_code in (429, 503) or r.status_code >= 500:
            time.sleep(int(r.headers.get('Retry-After', '0') or 0) or 2 * (attempt + 1))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r


def _store(rows: list[tuple], deleted: list[str] = ()):
    with database.get_connection() as conn:
        conn.executemany('INSERT OR REPLACE INTO zotero_index VALUES (?, ?, ?, ?)', rows)
        if deleted:
            conn.executemany('DELETE FROM zotero_index WHERE key = ?', [(k,) for k in deleted])
        conn.commit()


def _full_build(base: str, headers: dict) -> int:
    """처음 만들기: 최상위 항목을 100개씩 나눠 동시에 받음."""
    first = _get(f'{base}/items/top', headers, {'limit': 1})
    total = int(first.headers.get('Total-Results', '0'))
    version = int(first.headers.get('Last-Modified-Version', '0'))
    status.update(total=total, done=0)

    def page(start):
        r = _get(f'{base}/items/top', headers, {'limit': PAGE, 'start': start, 'format': 'json'})
        rows = [x for x in (_row(i) for i in r.json()) if x]
        _store(rows)
        status['done'] = min(total, status['done'] + PAGE)

    with ThreadPoolExecutor(WORKERS) as pool:
        list(pool.map(page, range(0, total, PAGE)))
    return version


def _incremental(base: str, headers: dict, since: int) -> int:
    """바뀐 항목과 지운 항목만 받아 갱신."""
    r = _get(f'{base}/items/top', headers, {'format': 'versions', 'since': since})
    version = int(r.headers.get('Last-Modified-Version', since))
    changed = list(r.json())
    status.update(total=len(changed), done=0)
    for i in range(0, len(changed), 50):
        chunk = changed[i:i + 50]
        items = _get(f'{base}/items', headers, {'itemKey': ','.join(chunk), 'format': 'json'}).json()
        _store([x for x in (_row(it) for it in items) if x])
        status['done'] += len(chunk)
    deleted = _get(f'{base}/deleted', headers, {'since': since}).json().get('items', [])
    _store([], deleted)
    return version


def sync(force_full: bool = False):
    """목록을 최신으로 맞춤. 이미 다른 스레드가 갱신 중이면 그것이 끝날 때까지 기다림."""
    with _lock:
        status.update(running=True, error=None)
        try:
            base, headers = zotero_client._config()
            since = 0 if force_full else int(_meta('version', '0'))
            version = _full_build(base, headers) if since == 0 else _incremental(base, headers, since)
            _set_meta(version=version, last_sync=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                      last_sync_ts=time.time())
        except Exception as e:
            status['error'] = str(e)
            raise
        finally:
            status['running'] = False


def sync_in_background(force_full: bool = False):
    def run():
        try:
            sync(force_full)
        except Exception:
            pass  # 오류는 status['error']에 남음
    threading.Thread(target=run, daemon=True).start()


def is_built() -> bool:
    return int(_meta('version', '0')) > 0


def refresh_if_stale():
    """목록이 이미 있고 마지막 갱신이 오래됐으면 바뀐 것만 받음 (몇 초)."""
    if is_built() and time.time() - float(_meta('last_sync_ts', '0')) > STALE_SECONDS:
        sync()


def find(paper: dict) -> str | None:
    """같은 논문이 Zotero에 있으면 항목 키를 돌려줌. DOI가 같거나 정규화 제목이 같으면 같은 논문."""
    doi = (paper.get('doi') or '').strip().lower()
    title = database.norm_title(paper.get('title'))
    with database.get_connection() as conn:
        if doi:
            row = conn.execute('SELECT key FROM zotero_index WHERE doi = ?', (doi,)).fetchone()
            if row:
                return row[0]
        if title:
            row = conn.execute('SELECT key FROM zotero_index WHERE title_norm = ?', (title,)).fetchone()
            if row:
                return row[0]
    return None


def add(key: str, paper: dict):
    """새로 만든 항목을 목록에 바로 반영 (다음 갱신을 기다리지 않음)."""
    _store([(key, (paper.get('doi') or '').lower() or None,
             database.norm_title(paper.get('title')), 'journalArticle')])
