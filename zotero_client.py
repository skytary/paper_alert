"""Zotero Web API 연동: 논문을 Zotero 항목으로 만들고 요약 메모를 붙인다."""
import html
import os
import re
import uuid

import requests

import enrich

ZOTERO_API_BASE = 'https://api.zotero.org'
TIMEOUT = 20


def _config() -> tuple[str, dict]:
    """(라이브러리 URL, 요청 헤더). 키나 ID가 없으면 ValueError."""
    api_key = os.getenv('ZOTERO_API_KEY', '').strip()
    user_id = os.getenv('ZOTERO_USER_ID', '').strip()
    library_type = os.getenv('ZOTERO_LIBRARY_TYPE', 'user').strip()
    if not api_key or not user_id:
        raise ValueError('ZOTERO_API_KEY and ZOTERO_USER_ID must be set in the .env file.')
    kind = 'groups' if library_type == 'group' else 'users'
    headers = {'Zotero-API-Key': api_key, 'Zotero-API-Version': '3'}
    return f'{ZOTERO_API_BASE}/{kind}/{user_id}', headers


def _creators_from_crossref(item: dict) -> list[dict]:
    creators = []
    for a in item.get('author', []):
        if a.get('family'):
            creators.append({'creatorType': 'author', 'firstName': a.get('given', ''),
                             'lastName': a['family']})
        elif a.get('name'):
            creators.append({'creatorType': 'author', 'name': a['name']})
    return creators


def _creators_from_text(authors: str | None) -> list[dict]:
    """'Jane Doe, John Smith and Kim Lee' 같은 저자 문자열을 이름/성으로 나눔 (마지막 단어를 성으로)."""
    creators = []
    for name in (authors or '').replace(' and ', ', ').split(','):
        parts = name.strip().split()
        if len(parts) >= 2:
            creators.append({'creatorType': 'author', 'firstName': ' '.join(parts[:-1]),
                             'lastName': parts[-1]})
        elif parts:
            creators.append({'creatorType': 'author', 'name': parts[0]})
    return creators


def build_item(paper: dict, collections: list[str] | None = None) -> dict:
    """Zotero journalArticle 항목. DOI가 있으면 Crossref 서지 정보로 채움."""
    cr = enrich.crossref_work(paper['doi']) if paper.get('doi') else None
    cr = cr or {}

    def first(key):
        value = cr.get(key) or []
        return value[0] if value else ''

    date = ''
    if cr:
        year = enrich.crossref_year(cr)
        date = str(year) if year else ''
    date = date or (str(paper['year']) if paper.get('year') else '')

    item = {
        'itemType': 'journalArticle',
        'title': first('title') or paper.get('title', ''),
        'creators': _creators_from_crossref(cr) or _creators_from_text(paper.get('authors')),
        'abstractNote': re.sub(r'^(Abstract|ABSTRACT)[:.]?\s+', '', paper.get('abstract') or ''),
        'publicationTitle': first('container-title') or paper.get('journal') or '',
        # Crossref가 약칭 자리에 전체 이름을 주는 경우가 많아, 전체 이름과 다를 때만 씀
        'journalAbbreviation': ('' if first('short-container-title') == first('container-title')
                                else first('short-container-title')),
        'volume': cr.get('volume', ''),
        'issue': cr.get('issue', ''),
        'pages': cr.get('page', ''),
        'date': date,
        'DOI': paper.get('doi') or '',
        'ISSN': ', '.join(cr.get('ISSN', [])),
        'url': cr.get('URL') or paper.get('link') or '',
        'tags': [{'tag': 'PaperAlert'}, {'tag': f"score:{paper.get('interest_score', '')}"}],
        'collections': collections or [],
    }
    return item


def build_note(paper: dict) -> str:
    """PaperAlert 평가 결과를 담은 HTML 메모."""
    def row(label, value):
        return f'<p><b>{label}:</b> {html.escape(str(value))}</p>' if value else ''
    return ('<h2>PaperAlert</h2>'
            + row('Score', paper.get('interest_score'))
            + row('Categories', paper.get('relevance_category'))
            + row('Summary', paper.get('summary_kr'))
            + row('Data', paper.get('field_data'))
            + row('Method', paper.get('method'))
            + row('Key findings', paper.get('key_findings'))
            + row('From email', paper.get('email_subject')))


def _post(url: str, headers: dict, objects: list[dict]) -> dict:
    """항목 생성 요청. Write-Token을 붙여 재시도해도 두 번 만들어지지 않게 함."""
    r = requests.post(url, json=objects, timeout=TIMEOUT,
                      headers={**headers, 'Zotero-Write-Token': uuid.uuid4().hex})
    r.raise_for_status()
    result = r.json()
    if result.get('successful'):
        return list(result['successful'].values())[0]
    failed = list((result.get('failed') or {}).values())
    message = failed[0].get('message', 'unknown error') if failed else 'unexpected response'
    raise ValueError(f'Zotero rejected the item: {message}')


FILLABLE = ['DOI', 'abstractNote', 'publicationTitle', 'journalAbbreviation', 'volume', 'issue',
            'pages', 'date', 'ISSN', 'url']


def fill_missing(key: str, paper: dict) -> list[str]:
    """이미 있는 Zotero 항목에서 비어 있는 서지 칸만 채움. 채운 칸 이름 목록을 돌려줌.

    이미 값이 있는 칸, 저자(이미 있으면), 태그, 메모, 첨부, 컬렉션은 건드리지 않는다.
    """
    base, headers = _config()
    r = requests.get(f'{base}/items/{key}', headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    current = r.json()['data']
    new = build_item(paper)
    patch = {f: new[f] for f in FILLABLE
             if f in current and not str(current.get(f) or '').strip() and new.get(f)}
    if not current.get('creators') and new.get('creators'):
        patch['creators'] = new['creators']
    if patch:
        r = requests.patch(f'{base}/items/{key}', json=patch, timeout=TIMEOUT,
                           headers={**headers, 'If-Unmodified-Since-Version': str(current['version'])})
        r.raise_for_status()
    return list(patch)


def add_paper(paper: dict, collections: list[str] | None = None) -> str:
    """논문을 Zotero에 새 항목으로 만들고 요약 메모를 붙인 뒤 항목 키를 돌려줌."""
    base, headers = _config()
    created = _post(f'{base}/items', headers, [build_item(paper, collections)])
    key = created['key']
    try:
        _post(f'{base}/items', headers,
              [{'itemType': 'note', 'parentItem': key, 'note': build_note(paper), 'tags': []}])
    except Exception:
        pass  # 항목은 이미 만들어졌으므로 메모 실패로 전체를 실패 처리하지 않음 (중복 생성 방지)
    return key
