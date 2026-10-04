"""Zotero로 보낼 때 어느 컬렉션에 넣을지 정한다 (설정의 보낼 곳 방식).

방식(zotero_target_mode)
- root: 라이브러리 루트 (컬렉션 없음)
- collection: 설정에서 고른 컬렉션 하나
- rules: PaperAlert 카테고리별로 대응시킨 컬렉션
- criteria: 분류 기준 파일(zotero_분류기준.md)을 보고 Claude가 고른 컬렉션
rules·criteria에서 맞는 곳이 없으면 zotero_fallback_collection(비어 있으면 루트)으로 보낸다.
"""
import json
import os
import re
import time

import requests

import database
import paper_processor
import zotero_client

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_SECONDS = 600
# 예전 형식의 상태 표시 중 '분류 대상 아님'을 뜻하는 것. 표시가 없으면 기준 문장이 있는 줄만 분류 대상
NOT_USED_MARKERS = {'제외', '제외 제안', '상위', 'exclude', 'excluded', 'parent', 'skip'}
# 줄 형식: "- 컬렉션 이름: 기준"  (기준이 없는 "- 컬렉션 이름" 줄은 상위·제외 폴더로 보고 분류에 안 씀)
# 이름 뒤의 [컬렉션 키], (n편), {상태 표시}는 모두 선택. 키는 같은 이름의 컬렉션이 여럿일 때만 필요
ITEM_RE = re.compile(r'^(\s*)[-*]\s+(.+?)\s*$')
# [키]나 {표시}가 있으면 그 앞까지가 이름 (이름에 콜론이 있어도 됨). 없으면 첫 ': ' 앞까지가 이름
TAGGED_RE = re.compile(r'^(.*?)\s*(?:\[([A-Z0-9]{8})\])?\s*(?:\(\d+[^)]*\))?\s*\{([^}]*)\}\s*(?::\s*(.*))?$')
KEYED_RE = re.compile(r'^(.*?)\s*\[([A-Z0-9]{8})\]\s*(?:\(\d+[^)]*\))?\s*()(?::\s*(.*))?$')
PLAIN_RE = re.compile(r'^(.*?)()\s*(?:\(\d+[^)]*\))?()\s*(?::\s*(.*))?$')

_collections_cache = {'at': 0.0, 'items': []}


# ── Zotero 컬렉션 목록 ───────────────────────────────────────────────────── #

def list_collections(refresh: bool = False) -> list[dict]:
    """[{key, name, path}] (경로 순). 10분 동안 메모리에 둠."""
    if not refresh and time.time() - _collections_cache['at'] < CACHE_SECONDS:
        return _collections_cache['items']
    base, headers = zotero_client._config()
    raw, start = [], 0
    while True:
        r = requests.get(f'{base}/collections', headers=headers,
                         params={'limit': 100, 'start': start}, timeout=30)
        r.raise_for_status()
        batch = r.json()
        raw += batch
        start += 100
        if len(batch) < 100:
            break
    by_key = {c['key']: c['data'] for c in raw}

    def path(key):
        parts = []
        while key:
            data = by_key.get(key)
            if not data:
                break
            parts.append(data['name'])
            key = data.get('parentCollection') or None
        return ' / '.join(reversed(parts))

    items = sorted(({'key': k, 'name': d['name'], 'path': path(k)} for k, d in by_key.items()),
                   key=lambda c: c['path'])
    _collections_cache.update(at=time.time(), items=items)
    return items


# ── 분류 기준 파일 ───────────────────────────────────────────────────────── #

def criteria_path(settings: dict | None = None) -> str:
    settings = settings or database.get_settings()
    path = settings['zotero_criteria_file']
    return path if os.path.isabs(path) else os.path.join(APP_DIR, path)


def parse_criteria(path: str) -> list[dict]:
    """기준 파일의 컬렉션 줄을 읽음: [{key, name, path, used, text}]. 경로는 들여쓰기로 만든다.

    used: 기준 문장이 있고 '제외'·'상위' 같은 표시가 없으면 True (분류 대상).
    """
    entries, stack = [], []
    with open(path, encoding='utf-8') as f:
        text = re.sub(r'<!--.*?-->', '', f.read(), flags=re.DOTALL)
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        m = ITEM_RE.match(line)
        if in_code or not m:
            continue
        item = m.group(2)
        parts = TAGGED_RE.match(item) or KEYED_RE.match(item) or PLAIN_RE.match(item)
        name = (parts.group(1) or '').strip()
        if not name or name.startswith('`'):   # 설명용 목록(`{표시}` 등)은 컬렉션 줄이 아님
            continue
        depth = len(m.group(1).expandtabs(2)) // 2
        stack = stack[:depth] + [name]
        marker = (parts.group(3) or '').strip().lower()
        criterion = (parts.group(4) or '').strip()
        entries.append({'key': parts.group(2) or None, 'name': name, 'path': ' / '.join(stack),
                        'used': bool(criterion) and marker not in NOT_USED_MARKERS,
                        'text': criterion})
    return entries


def resolve_keys(entries: list[dict]) -> list[dict]:
    """키가 없는 줄은 경로(없으면 이름)가 같은 Zotero 컬렉션의 키로 채움.

    찾으면 e['by_name'] = True, 못 찾거나 같은 이름이 여러 개면 e['key'] = None, e['problem']에 이유.
    """
    if all(e['key'] for e in entries):
        return entries
    cols = list_collections()
    by_path = {c['path']: c['key'] for c in cols}
    by_name = {}
    for c in cols:
        by_name.setdefault(c['name'], []).append(c['key'])
    for e in entries:
        if e['key']:
            continue
        if e['path'] in by_path:
            e['key'], e['by_name'] = by_path[e['path']], True
        elif len(by_name.get(e['name'], [])) == 1:
            e['key'], e['by_name'] = by_name[e['name']][0], True
        else:
            n = len(by_name.get(e['name'], []))
            e['problem'] = ('no Zotero collection with this name' if n == 0 else
                            f'{n} Zotero collections share this name; add the [key]')
    return entries


def criteria_status(settings: dict | None = None) -> dict:
    """기준 파일 검사 결과: 상태별 개수, Zotero에 없는 키, 파일에 없는 컬렉션."""
    path = criteria_path(settings)
    if not os.path.exists(path):
        return {'ok': False, 'error': f'File not found: {path}'}
    entries = parse_criteria(path)
    if not entries:
        return {'ok': False, 'error': 'No collection lines found in the file.'}
    usable = sum(1 for e in entries if e['used'])
    result = {'ok': True, 'path': path, 'entries': len(entries), 'usable': usable,
              'not_used': len(entries) - usable}
    try:
        entries = resolve_keys(entries)
        zotero = {c['key']: c for c in list_collections()}
        in_file = {e['key'] for e in entries if e['key']}
        result['matched_by_name'] = [e['path'] for e in entries if e.get('by_name')]
        result['unresolved'] = [f"{e['path']} ({e['problem']})" for e in entries if e.get('problem')]
        result['missing_in_zotero'] = [e['path'] for e in entries
                                       if e['key'] and e['key'] not in zotero]
        # 파일에 나온 최상위 폴더 아래에 새로 생긴 컬렉션
        roots = {e['path'].split(' / ')[0] for e in entries}
        result['not_in_file'] = [c['path'] for c in zotero.values()
                                 if c['key'] not in in_file and c['path'].split(' / ')[0] in roots]
    except Exception as ex:
        result['zotero_error'] = str(ex)
    return result


CLASSIFY_SYSTEM = """You file academic papers into a researcher's Zotero collections.

You will receive a list of collections (key, path, and the criterion describing which papers belong there), and one paper.
Choose EVERY collection whose criterion clearly fits the paper. A paper often fits several collections, including collections in different top-level folders. Prefer the most specific subcollection that fits; add a parent collection only if the paper fits the parent's own criterion as well.
If no criterion clearly fits, return an empty list. Do not force a match.
Use only keys from the list."""

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "collections": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
    },
    "required": ["collections", "reason"],
    "additionalProperties": False,
}


def classify_by_criteria(paper: dict, settings: dict | None = None) -> list[str]:
    """기준 파일을 보고 Claude가 고른 컬렉션 키 목록. 맞는 곳이 없으면 빈 목록."""
    entries = [e for e in resolve_keys(parse_criteria(criteria_path(settings)))
               if e['used'] and e['key']]
    allowed = {e['key'] for e in entries}
    listing = '\n'.join(f"[{e['key']}] {e['path']}: {e['text']}" for e in entries)
    paper_text = '\n'.join(f'{label}: {paper.get(field)}' for label, field in [
        ('Title', 'title'), ('Authors', 'authors'), ('Journal', 'journal'), ('Year', 'year'),
        ('Abstract', 'abstract'), ('Summary', 'summary_kr'), ('Data', 'field_data'),
        ('Method', 'method'), ('Key findings', 'key_findings')] if paper.get(field))
    # 기준 목록은 시스템 프롬프트에 넣어 캐싱 (논문마다 같음)
    result = paper_processor._call(CLASSIFY_SYSTEM + '\n\n--- Collections ---\n' + listing,
                                   'Paper:\n' + paper_text, CLASSIFY_SCHEMA, 'low',
                                   (paper.get('title') or '')[:60])
    return [k for k in dict.fromkeys(result['collections']) if k in allowed]


# ── 최종 보낼 곳 ─────────────────────────────────────────────────────────── #

def resolve(paper: dict, settings: dict | None = None) -> list[str]:
    """설정한 방식에 따라 이 논문을 넣을 컬렉션 키 목록 (빈 목록 = 루트)."""
    settings = settings or database.get_settings()
    mode = settings['zotero_target_mode']
    fallback = [settings['zotero_fallback_collection']] if settings['zotero_fallback_collection'] else []

    if mode == 'collection':
        return [settings['zotero_target_collection']] if settings['zotero_target_collection'] else []
    if mode == 'rules':
        rules = json.loads(settings['zotero_rules'] or '{}')
        cats = [c.strip() for c in (paper.get('relevance_category') or '').split(',') if c.strip()]
        keys = list(dict.fromkeys(rules[c] for c in cats if rules.get(c)))
        return keys or fallback
    if mode == 'criteria':
        return classify_by_criteria(paper, settings) or fallback
    return []
