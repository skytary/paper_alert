"""배치 처리: 메일을 Message Batches API로 보내 반값에 처리한다.

처리가 두 단계라 배치도 두 번 돈다.
  1) extract 배치: 메일마다 논문 목록 뽑기
  2) 결과가 오면 DOI·초록 보강, 이미 있는 논문 거르기 (앱에서 바로)
  3) score 배치: 새 논문이 있는 메일만 평가
  4) 결과가 오면 저장, 메일 읽음 처리·처리 완료 기록
진행 상황은 DB(batch_jobs, batch_emails)에 남겨 앱을 껐다 켜도 이어서 처리한다.
실패·만료된 메일은 기록에서 지워져 다음 Fetch 때 다시 처리된다.
"""
import json
import threading
import time
from datetime import datetime

import database
import gmail_client
import paper_processor

POLL_SECONDS = 60

_lock = threading.Lock()
_poller_started = False
state = {'last_check': '', 'last_message': '', 'errors': []}


def init_tables():
    with database.get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS batch_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stage TEXT,              -- extract / score
                batch_id TEXT,           -- Anthropic 배치 ID
                status TEXT,             -- in_progress / done
                created_at TEXT,
                finished_at TEXT,
                n_requests INTEGER
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS batch_emails (
                email_id TEXT PRIMARY KEY,
                job_id INTEGER,
                stage TEXT,              -- extract / score
                subject TEXT,
                received_at TEXT,
                body TEXT,
                papers_json TEXT,        -- score 단계에서 평가할 논문
                skipped INTEGER DEFAULT 0
            )
        ''')
        conn.commit()


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def active_email_ids() -> set[str]:
    with database.get_connection() as conn:
        return {r[0] for r in conn.execute('SELECT email_id FROM batch_emails')}


def summary() -> dict:
    with database.get_connection() as conn:
        rows = conn.execute('SELECT stage, COUNT(*) FROM batch_emails GROUP BY stage').fetchall()
        jobs = conn.execute("SELECT COUNT(*) FROM batch_jobs WHERE status = 'in_progress'").fetchone()[0]
    by_stage = dict(rows)
    return {'emails': sum(by_stage.values()), 'extract': by_stage.get('extract', 0),
            'score': by_stage.get('score', 0), 'jobs': jobs, **state}


def _email(row) -> dict:
    return {'id': row['email_id'], 'subject': row['subject'] or '',
            'received_at': row['received_at'] or '', 'body': row['body'] or ''}


def _create_batch(stage: str, requests_: list[dict]) -> int:
    """배치를 만들고 job id를 돌려줌."""
    batch = paper_processor._get_client().messages.batches.create(requests=requests_)
    with database.get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO batch_jobs (stage, batch_id, status, created_at, n_requests) "
            "VALUES (?, ?, 'in_progress', ?, ?)", (stage, batch.id, _now(), len(requests_)))
        conn.commit()
        return cur.lastrowid


def submit(email_ids: list[str], progress=None) -> int:
    """메일들의 1단계(목록 뽑기)를 배치로 보냄. 보낸 메일 수를 돌려줌."""
    emails = []
    for i, email_id in enumerate(email_ids):
        if progress:
            progress(i + 1, len(email_ids))
        try:
            emails.append(gmail_client.get_email_content_by_id(email_id))
        except Exception as e:
            state['errors'].append(f'Could not load email {email_id}: {e}')
    if not emails:
        return 0
    requests_ = [{'custom_id': e['id'],
                  'params': paper_processor.request_params(*paper_processor.extract_request(e))}
                 for e in emails]
    with _lock:
        job_id = _create_batch('extract', requests_)
        with database.get_connection() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO batch_emails (email_id, job_id, stage, subject, received_at, body) "
                "VALUES (?, ?, 'extract', ?, ?, ?)",
                [(e['id'], job_id, e.get('subject', ''), e.get('received_at', ''), e.get('body', ''))
                 for e in emails])
            conn.commit()
    state['last_message'] = f'{_now()}: submitted {len(emails)} emails as a batch (step 1 of 2).'
    return len(emails)


def _finish_email(email_id: str, papers_found: int):
    """메일 처리 완료: 읽음 처리, 처리 완료 기록, 배치 기록 삭제."""
    gmail_client.mark_email_read(email_id)
    database.mark_email_processed(email_id, papers_found)
    with database.get_connection() as conn:
        conn.execute('DELETE FROM batch_emails WHERE email_id = ?', (email_id,))
        conn.commit()


def _drop_email(email_id: str, reason: str):
    """실패한 메일은 기록에서 지워 다음 Fetch 때 다시 처리되게 함."""
    state['errors'].append(f'{email_id}: {reason}')
    with database.get_connection() as conn:
        conn.execute('DELETE FROM batch_emails WHERE email_id = ?', (email_id,))
        conn.commit()


def _results(batch_id: str) -> dict:
    """{custom_id: 결과}"""
    return {r.custom_id: r.result
            for r in paper_processor._get_client().messages.batches.results(batch_id)}


def _handle_extract(job, rows: dict, on_saved) -> str:
    results = _results(job['batch_id'])
    language = database.get_settings()['summary_language']
    to_score, finished = [], 0
    for email_id, row in rows.items():
        result = results.get(email_id)
        if result is None or result.type != 'succeeded':
            _drop_email(email_id, f'step 1 {getattr(result, "type", "missing")}')
            continue
        try:
            papers = paper_processor.parse_extract(
                paper_processor.parse_response(result.message, row['subject'][:60]))
            new, skipped = paper_processor.enrich_and_dedupe(papers)
        except Exception as e:
            _drop_email(email_id, f'step 1 failed: {e}')
            continue
        if not new:
            _finish_email(email_id, skipped)
            finished += 1
            continue
        to_score.append((email_id, new, skipped,
                         {'custom_id': email_id,
                          'params': paper_processor.request_params(
                              *paper_processor.score_request(new, _email(row), language))}))
    if to_score:
        # 배치를 만든 뒤에 기록을 바꿈. 만들다 실패하면 예외가 나서 다음 확인 때 이 단계를 다시 함
        job_id = _create_batch('score', [req for *_, req in to_score])
        with database.get_connection() as conn:
            conn.executemany(
                "UPDATE batch_emails SET stage = 'score', job_id = ?, papers_json = ?, skipped = ? "
                "WHERE email_id = ?",
                [(job_id, json.dumps(new, ensure_ascii=False), skipped, email_id)
                 for email_id, new, skipped, _ in to_score])
            conn.commit()
    return (f'step 1 done: {len(to_score)} emails sent for scoring (step 2 of 2), '
            f'{finished} had no new papers.')


def _handle_score(job, rows: dict, on_saved) -> str:
    results = _results(job['batch_id'])
    saved_total = 0
    for email_id, row in rows.items():
        result = results.get(email_id)
        if result is None or result.type != 'succeeded':
            _drop_email(email_id, f'step 2 {getattr(result, "type", "missing")}')
            continue
        try:
            papers = json.loads(row['papers_json'])
            email = _email(row)
            scored = paper_processor.merge_scores(
                papers, paper_processor.parse_response(result.message, row['subject'][:60]), email)
        except Exception as e:
            _drop_email(email_id, f'step 2 failed: {e}')
            continue
        new_ids = []
        for p in scored:
            paper_id = database.save_paper(p)
            if paper_id:
                new_ids.append((paper_id, p.get('interest_score') or 0))
        saved_total += len(new_ids)
        _finish_email(email_id, len(scored) + (row['skipped'] or 0))
        if on_saved:
            on_saved(new_ids)
    return f'step 2 done: {saved_total} papers saved.'


def poll(on_saved=None) -> str:
    """진행 중인 배치를 확인하고, 끝난 배치는 다음 단계로 넘기거나 저장을 마무리함."""
    messages = []
    with _lock:
        with database.get_connection() as conn:
            jobs = conn.execute("SELECT * FROM batch_jobs WHERE status = 'in_progress'").fetchall()
        for job in jobs:
            batch = paper_processor._get_client().messages.batches.retrieve(job['batch_id'])
            if batch.processing_status != 'ended':
                continue
            with database.get_connection() as conn:
                rows = {r['email_id']: r for r in conn.execute(
                    'SELECT * FROM batch_emails WHERE job_id = ? AND stage = ?',
                    (job['id'], job['stage']))}
            handler = _handle_extract if job['stage'] == 'extract' else _handle_score
            messages.append(handler(job, rows, on_saved))
            with database.get_connection() as conn:
                conn.execute("UPDATE batch_jobs SET status = 'done', finished_at = ? WHERE id = ?",
                             (_now(), job['id']))
                conn.commit()
    state['last_check'] = _now()
    if messages:
        state['last_message'] = f"{_now()}: " + ' '.join(messages)
    return ' '.join(messages)


def start_poller(on_saved=None):
    """앱이 켜져 있는 동안 1분마다 배치를 확인 (한 번만 시작)."""
    global _poller_started
    if _poller_started:
        return
    _poller_started = True

    def loop():
        while True:
            try:
                poll(on_saved)
            except Exception as e:
                state['errors'].append(f'{_now()}: batch check failed: {e}')
                del state['errors'][:-20]
            time.sleep(POLL_SECONDS)
    threading.Thread(target=loop, daemon=True).start()
