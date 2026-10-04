"""SQLite 데이터베이스 관리 모듈"""
import json
import re
import sqlite3
import unicodedata
from datetime import datetime

DB_PATH = 'papers.db'

# 카테고리는 연구 관심사 프로필(research_profile.md)의 Categories 절에서 읽어 추가한다
# (research_profile.sync_categories). 여기에는 기본값을 두지 않는다.
DEFAULT_CATEGORIES: list[str] = []


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT NOT NULL,
                email_subject TEXT,
                title TEXT NOT NULL,
                authors TEXT,
                journal TEXT,
                year INTEGER,
                doi TEXT,
                abstract TEXT,
                interest_score INTEGER,
                score_reason TEXT,
                summary_kr TEXT,
                method TEXT,
                field_data TEXT,
                key_findings TEXT,
                relevance_category TEXT,
                link TEXT,
                email_received_at TEXT,
                processed_at TEXT,
                added_to_zotero INTEGER DEFAULT 0,
                zotero_key TEXT,
                UNIQUE(email_id, title)
            )
        ''')
        _migrate(conn)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS processed_emails (
                email_id TEXT PRIMARY KEY,
                processed_at TEXT,
                papers_found INTEGER DEFAULT 0
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')
        # 기본 카테고리 삽입 (없을 경우만)
        for cat in DEFAULT_CATEGORIES:
            conn.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (cat,))
        conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        conn.commit()


# ── 설정 ─────────────────────────────────────────────────────────────────── #
# 키와 기본값. 여기에 없는 키는 저장하지 않는다.
DEFAULT_SETTINGS = {
    'summary_language': 'Korean',     # 요약·데이터·주요 발견을 쓸 언어: Korean / English
    'research_profile_file': 'research_profile.md',  # 연구 관심사 프로필 (앱 폴더 기준 상대 경로 가능)
    'start_date': '',                 # 이 날짜(YYYY-MM-DD) 이후에 받은 메일만 처리. 빈 값이면 전부
    'batch_size': '50',               # 한 번에 처리할 메일 수. 'all'이면 전부
    'fetch_order': 'newest',          # 처리 순서: newest(최신부터) / oldest(오래된 것부터)
    'fetch_mode': 'instant',          # instant(바로 처리) / batch(배치 API, 반값, 결과는 몇 분~몇 시간 뒤)
    'zotero_enabled': 'on',           # Zotero 보내기 기능 전체 켜기/끄기
    'zotero_auto_min_score': 'off',   # Fetch 때 이 점수 이상이면 자동으로 보냄. off면 자동 보내기 안 함
    'zotero_existing': 'skip',        # Zotero에 이미 있는 논문: skip(새로 만들지 않음) / fill(빈 서지 칸만 채움)
    # 보낼 곳 (zotero_targets.py 참고)
    'zotero_target_mode': 'root',     # root / collection / rules / criteria
    'zotero_target_collection': '',   # collection 방식의 컬렉션 키
    'zotero_rules': '{}',             # rules 방식: {"카테고리": "컬렉션 키"} JSON
    'zotero_criteria_file': 'zotero_분류기준.md',   # criteria 방식의 기준 파일 (앱 폴더 기준 상대 경로 가능)
    'zotero_fallback_collection': '', # rules·criteria에서 맞는 곳이 없을 때 컬렉션 키 (비면 루트)
}
SETTING_CHOICES = {
    'summary_language': ['Korean', 'English'],
    'batch_size': ['10', '25', '50', '100', '200', '500', 'all'],
    'fetch_order': ['newest', 'oldest'],
    'fetch_mode': ['instant', 'batch'],
    'zotero_enabled': ['on', 'off'],
    'zotero_auto_min_score': ['off', '5', '4', '3'],
    'zotero_existing': ['skip', 'fill'],
    'zotero_target_mode': ['root', 'collection', 'rules', 'criteria'],
}


def _valid_date(value: str) -> bool:
    if value == '':
        return True
    try:
        datetime.strptime(value, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def _valid_collection_key(value: str) -> bool:
    return value == '' or bool(re.fullmatch(r'[A-Z0-9]{8}', value))


def _valid_rules(value: str) -> bool:
    try:
        rules = json.loads(value)
    except ValueError:
        return False
    return isinstance(rules, dict) and all(
        isinstance(k, str) and isinstance(v, str) and _valid_collection_key(v) for k, v in rules.items())


# 선택지가 아닌 값을 받는 설정의 검사 함수
SETTING_VALIDATORS = {
    'start_date': _valid_date,
    'zotero_target_collection': _valid_collection_key,
    'zotero_fallback_collection': _valid_collection_key,
    'zotero_rules': _valid_rules,
    'zotero_criteria_file': lambda v: v.strip() != '',
    'research_profile_file': lambda v: v.strip() != '',
}


def get_settings() -> dict:
    """저장된 설정(없으면 기본값)을 모두 돌려줌."""
    with get_connection() as conn:
        rows = dict(conn.execute('SELECT key, value FROM settings').fetchall())
    return {k: rows.get(k, v) for k, v in DEFAULT_SETTINGS.items()}


def update_settings(values: dict) -> dict:
    """알려진 키만 검사해서 저장하고, 저장 후 전체 설정을 돌려줌. 잘못된 값은 ValueError."""
    for key, value in values.items():
        if key not in DEFAULT_SETTINGS:
            raise ValueError(f'Unknown setting: {key}')
        value = str(value)
        values[key] = value
        choices = SETTING_CHOICES.get(key)
        validator = SETTING_VALIDATORS.get(key)
        if (choices and value not in choices) or (validator and not validator(value)):
            raise ValueError(f'Invalid value for {key}: {value}')
    with get_connection() as conn:
        for key, value in values.items():
            conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                         (key, str(value)))
        conn.commit()
    return get_settings()


def _migrate(conn):
    """기존 DB에 새 컬럼 추가 (없을 경우만)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
    new_cols = [
        ("summary_kr",         "TEXT"),
        ("method",             "TEXT"),
        ("field_data",         "TEXT"),
        ("key_findings",       "TEXT"),
        ("relevance_category", "TEXT"),
        ("link",               "TEXT"),
        ("is_checked",         "INTEGER DEFAULT 0"),
    ]
    for col_name, col_type in new_cols:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE papers ADD COLUMN {col_name} {col_type}")


def norm_title(title: str | None) -> str:
    """중복 비교용 제목: 악센트·문장부호·따옴표 모양·띄어쓰기·대소문자 차이를 없앰.

    곧은 따옴표(don't)와 둥근 따옴표(don’t)가 같게 나오도록 영숫자만 남기고 붙여 씀.
    """
    text = unicodedata.normalize('NFKD', title or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '', text.lower())


def existing_keys() -> tuple[set[str], set[str]]:
    """DB에 있는 논문의 (DOI 집합, 정규화 제목 집합). DOI는 소문자."""
    with get_connection() as conn:
        rows = conn.execute('SELECT doi, title FROM papers').fetchall()
    dois = {r[0].lower() for r in rows if r[0]}
    titles = {norm_title(r[1]) for r in rows if r[1]}
    return dois, titles


def is_duplicate(paper: dict, keys: tuple[set[str], set[str]] | None = None) -> bool:
    """DOI가 같거나 정규화 제목이 같은 논문이 이미 DB에 있으면 True."""
    dois, titles = keys or existing_keys()
    doi = (paper.get('doi') or '').strip().lower()
    return bool(doi and doi in dois) or norm_title(paper.get('title')) in titles


def save_paper(paper: dict) -> int | None:
    """논문을 DB에 저장하고 ID를 반환. 중복(DOI 또는 정규화 제목)이면 None 반환."""
    if is_duplicate(paper):
        return None  # 타 이메일 포함 전체 중복

    with get_connection() as conn:

        try:
            cursor = conn.execute('''
                INSERT INTO papers (
                    email_id, email_subject, title, authors, journal, year,
                    doi, abstract, interest_score, score_reason,
                    summary_kr, method, field_data, key_findings,
                    relevance_category, link,
                    email_received_at, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                paper.get('email_id'),
                paper.get('email_subject'),
                paper.get('title', '').strip(),
                paper.get('authors'),
                paper.get('journal'),
                paper.get('year'),
                paper.get('doi'),
                paper.get('abstract'),
                paper.get('interest_score'),
                paper.get('score_reason'),
                paper.get('summary_kr'),
                paper.get('method'),
                paper.get('field_data'),
                paper.get('key_findings'),
                paper.get('relevance_category'),
                paper.get('link'),
                paper.get('email_received_at'),
                paper.get('processed_at', datetime.now().isoformat()),
            ))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None  # 중복 논문


def is_email_processed(email_id: str) -> bool:
    with get_connection() as conn:
        result = conn.execute(
            'SELECT 1 FROM processed_emails WHERE email_id = ?', (email_id,)
        ).fetchone()
        return result is not None


def processed_email_ids() -> set[str]:
    with get_connection() as conn:
        return {r[0] for r in conn.execute('SELECT email_id FROM processed_emails')}


def mark_email_processed(email_id: str, papers_found: int):
    with get_connection() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO processed_emails (email_id, processed_at, papers_found)
            VALUES (?, ?, ?)
        ''', (email_id, datetime.now().isoformat(), papers_found))
        conn.commit()


def get_papers(min_score=1, journal=None, year=None,
               sort_by='interest_score', order='DESC',
               search=None, category=None, checked=None) -> list[dict]:
    query = 'SELECT * FROM papers WHERE interest_score >= ?'
    params: list = [min_score]

    if journal:
        query += ' AND journal LIKE ?'
        params.append(f'%{journal}%')

    if year:
        query += ' AND year = ?'
        params.append(int(year))

    if search:
        query += ' AND (title LIKE ? OR authors LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])

    if category:
        # 콤마 구분 문자열에서 특정 카테고리 포함 여부 검색
        query += " AND (',' || COALESCE(relevance_category,'') || ',' LIKE ?)"
        params.append(f'%,{category},%')

    if checked is not None:
        query += ' AND COALESCE(is_checked, 0) = ?'
        params.append(int(checked))

    allowed_sort = {'interest_score', 'processed_at', 'year', 'journal', 'title'}
    if sort_by not in allowed_sort:
        sort_by = 'interest_score'
    if order not in ('ASC', 'DESC'):
        order = 'DESC'

    query += f' ORDER BY {sort_by} {order}, id DESC LIMIT 500'

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_paper_by_id(paper_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute('SELECT * FROM papers WHERE id = ?', (paper_id,)).fetchone()
        return dict(row) if row else None


def update_paper_score(paper_id: int, score: int):
    """논문 점수 업데이트."""
    score = max(1, min(5, int(score)))
    with get_connection() as conn:
        conn.execute('UPDATE papers SET interest_score = ? WHERE id = ?', (score, paper_id))
        conn.commit()


def update_paper_checked(paper_id: int, checked: int):
    """논문 확인 여부 업데이트 (0=미확인, 1=확인)."""
    with get_connection() as conn:
        conn.execute('UPDATE papers SET is_checked = ? WHERE id = ?',
                     (1 if checked else 0, paper_id))
        conn.commit()


def update_paper_metadata(paper_id: int, doi: str | None, abstract: str | None, year: int | None):
    """보강으로 찾은 DOI·초록·연도를 비어 있는 칸에만 채움."""
    with get_connection() as conn:
        conn.execute('''
            UPDATE papers SET doi = COALESCE(doi, ?), abstract = COALESCE(abstract, ?),
                              year = COALESCE(year, ?)
            WHERE id = ?
        ''', (doi, abstract, year, paper_id))
        conn.commit()


def mark_paper_in_zotero(paper_id: int, zotero_key: str):
    with get_connection() as conn:
        conn.execute('UPDATE papers SET added_to_zotero = 1, zotero_key = ? WHERE id = ?',
                     (zotero_key, paper_id))
        conn.commit()


def update_paper_categories(paper_id: int, categories_str: str):
    """논문 카테고리 업데이트 (콤마 구분 문자열)."""
    with get_connection() as conn:
        conn.execute('UPDATE papers SET relevance_category = ? WHERE id = ?',
                     (categories_str or None, paper_id))
        conn.commit()


def get_categories() -> list[str]:
    """모든 카테고리 목록 반환 (등록 순서)."""
    with get_connection() as conn:
        rows = conn.execute('SELECT name FROM categories ORDER BY id').fetchall()
        return [row[0] for row in rows]


def add_category(name: str) -> bool:
    """카테고리 추가. 이미 있으면 False 반환."""
    try:
        with get_connection() as conn:
            conn.execute('INSERT INTO categories (name) VALUES (?)', (name.strip(),))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def delete_category(name: str):
    """카테고리 삭제."""
    with get_connection() as conn:
        conn.execute('DELETE FROM categories WHERE name = ?', (name,))
        conn.commit()


def get_stats() -> dict:
    with get_connection() as conn:
        total = conn.execute('SELECT COUNT(*) FROM papers').fetchone()[0]

        journals = [r[0] for r in conn.execute(
            'SELECT DISTINCT journal FROM papers WHERE journal IS NOT NULL ORDER BY journal'
        ).fetchall()]

        years = [r[0] for r in conn.execute(
            'SELECT DISTINCT year FROM papers WHERE year IS NOT NULL ORDER BY year DESC'
        ).fetchall()]

        high_interest = conn.execute(
            'SELECT COUNT(*) FROM papers WHERE interest_score >= 4'
        ).fetchone()[0]

        unchecked = conn.execute(
            'SELECT COUNT(*) FROM papers WHERE COALESCE(is_checked, 0) = 0'
        ).fetchone()[0]

        # 카테고리별 논문 수 (콤마 구분 문자열 파싱)
        all_cats = get_categories()
        cat_counts: dict[str, int] = {}
        rows = conn.execute(
            'SELECT relevance_category FROM papers WHERE relevance_category IS NOT NULL'
        ).fetchall()
        for row in rows:
            for c in [x.strip() for x in row[0].split(',') if x.strip()]:
                cat_counts[c] = cat_counts.get(c, 0) + 1

        category_stats = [
            {'name': cat, 'count': cat_counts.get(cat, 0)}
            for cat in all_cats
        ]

        return {
            'total': total,
            'high_interest': high_interest,
            'unchecked': unchecked,
            'journals': journals,
            'years': years,
            'category_stats': category_stats,
        }
