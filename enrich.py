"""논문 정보 보강: Crossref에서 DOI·연도를, OpenAlex에서 초록을 가져온다.

알림 메일에는 초록이 없거나 링크가 추적용 우회 주소라 DOI가 드러나지 않는 경우가 많다.
제목만으로 찾으면 같은 연구의 워킹페이퍼·프리프린트·데이터셋이 잡히므로,
학술지 논문(journal-article)만 찾고 제목 유사도와 학술지 이름 또는 저자 성까지 맞춰 본다.
네트워크 오류나 검색 실패는 예외 없이 None으로 돌려준다(메일 처리를 막지 않음).
"""
import re
import time
import unicodedata
from difflib import SequenceMatcher

import requests

CROSSREF = 'https://api.crossref.org/works'
OPENALEX = 'https://api.openalex.org/works'
HEADERS = {'User-Agent': 'PaperAlert/1.0'}
TIMEOUT = 20
MIN_INTERVAL = 0.25          # Crossref 요청 사이 최소 간격(초)

TITLE_SIM = 0.9              # 제목 유사도 기준
JOURNAL_SIM = 0.8            # 학술지 이름 유사도 기준

DOI_RE = re.compile(r'\b(10\.\d{4,9}/[^\s<>"\'?#&]+)', re.IGNORECASE)

_last_call = 0.0


def norm_text(text: str | None) -> str:
    """비교용 정규화: 악센트 제거, 소문자, 영숫자만 남김."""
    text = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


def _sim(a: str | None, b: str | None) -> float:
    return SequenceMatcher(None, norm_text(a), norm_text(b)).ratio()


def _surnames(authors: str | None) -> set[str]:
    names = re.split(r',| and |;|&', authors or '')
    return {norm_text(n).split()[-1] for n in names if norm_text(n)}


def doi_from_text(text: str | None) -> str | None:
    """링크 등 문자열에 그대로 들어 있는 DOI를 찾음 (doi.org/10.xxx, /doi/10.xxx)."""
    m = DOI_RE.search(text or '')
    return m.group(1).rstrip('.,;)') if m else None


def _get(url: str, params: dict | None = None) -> dict | None:
    """GET 요청. 429·5xx는 잠시 기다렸다가 두 번까지 다시 시도."""
    global _last_call
    for attempt in range(3):
        wait = MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return None
        if r.status_code == 429 or r.status_code >= 500:
            retry_after = r.headers.get('Retry-After', '')
            time.sleep(int(retry_after) if retry_after.isdigit() else 3 * (attempt + 1))
            continue
        return None
    return None


def _year(item: dict) -> int | None:
    for key in ('published-print', 'published-online', 'issued'):
        parts = (item.get(key) or {}).get('date-parts') or [[None]]
        if parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def _strip_jats(text: str | None) -> str | None:
    """Crossref 초록의 JATS 태그(<jats:p> 등)를 지움."""
    if not text:
        return None
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'^(Abstract|ABSTRACT)\s*', '', text)
    return text or None


def _openalex_abstract(doi: str) -> str | None:
    """OpenAlex의 역색인(abstract_inverted_index)을 원래 문장으로 되돌림."""
    data = _get(f'{OPENALEX}/doi:{doi}')
    index = (data or {}).get('abstract_inverted_index')
    if not index:
        return None
    words = sorted((pos, word) for word, positions in index.items() for pos in positions)
    text = ' '.join(word for _, word in words)
    return re.sub(r'^(Abstract|ABSTRACT)[:.]?\s+', '', text) or None


def _crossref_by_doi(doi: str) -> dict | None:
    data = _get(f'{CROSSREF}/{doi}')
    return (data or {}).get('message')


def crossref_work(doi: str) -> dict | None:
    """DOI의 Crossref 서지 정보(message). 없거나 오류면 None."""
    return _crossref_by_doi(doi)


def crossref_year(item: dict) -> int | None:
    return _year(item)


def _crossref_search(title: str, journal: str | None, authors: str | None) -> dict | None:
    params = {'query.bibliographic': title, 'rows': 5, 'filter': 'type:journal-article'}
    if journal:
        params['query.container-title'] = journal
    data = _get(CROSSREF, params)
    want = _surnames(authors)
    for item in ((data or {}).get('message') or {}).get('items', []):
        if _sim((item.get('title') or [''])[0], title) < TITLE_SIM:
            continue
        venue = (item.get('container-title') or [''])[0]
        journal_ok = bool(journal) and _sim(venue, journal) >= JOURNAL_SIM
        family = {norm_text(a.get('family', '')) for a in item.get('author', [])}
        author_ok = bool(want & family)
        if journal_ok or author_ok:
            return item
    return None


def enrich(paper: dict) -> dict:
    """논문 하나의 DOI·연도·초록을 찾아서 채운 새 dict를 돌려줌.

    링크에 DOI가 그대로 있으면 그것을 믿고, 없으면 Crossref에서 제목으로 찾는다.
    찾지 못하면 원래 값을 그대로 둔다.
    """
    out = dict(paper)
    doi = doi_from_text(paper.get('link'))
    item = _crossref_by_doi(doi) if doi else None
    if not item:
        item = _crossref_search(paper.get('title', ''), paper.get('journal'), paper.get('authors'))
        if item:
            doi = item.get('DOI')
        # Crossref에 없는 DOI(DataCite의 프리프린트 등)는 링크에서 찾은 값을 그대로 씀
    if not doi:
        return out

    out['doi'] = doi.lower()
    if item:
        out['year'] = _year(item) or out.get('year')
    abstract = _openalex_abstract(doi) or _strip_jats((item or {}).get('abstract'))
    if abstract:
        out['abstract'] = abstract
    return out
