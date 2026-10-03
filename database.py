"""SQLite 데이터베이스 관리 모듈"""
import sqlite3
from datetime import datetime

DB_PATH = 'papers.db'

DEFAULT_CATEGORIES = [
    "Core: Research",
    "Method: Causal/Advanced",
    "Class: Stratification",
    "Class: Education",
    "Class: Social Research Methods",
    "General Interest",
]


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
        conn.commit()


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


def save_paper(paper: dict) -> int | None:
    """논문을 DB에 저장하고 ID를 반환. 중복이면 None 반환."""
    title = paper.get('title', '').strip()
    doi   = paper.get('doi', '').strip() if paper.get('doi') else ''

    with get_connection() as conn:
        # 제목(대소문자 무관) 또는 DOI 기준 중복 확인
        if doi:
            dup = conn.execute(
                'SELECT id FROM papers WHERE doi = ? OR LOWER(title) = LOWER(?)',
                (doi, title)
            ).fetchone()
        else:
            dup = conn.execute(
                'SELECT id FROM papers WHERE LOWER(title) = LOWER(?)',
                (title,)
            ).fetchone()
        if dup:
            return None  # 타 이메일 포함 전체 중복

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
