"""PaperAlert - 학술 논문 알림 처리 웹앱"""
import os
import threading
import webbrowser
import time
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv

load_dotenv()

import database
import enrich
import gmail_client
import paper_processor
import zotero_client
import zotero_index

app = Flask(__name__)
database.init_db()
zotero_index.init_tables()

# ── 처리 상태 ─────────────────────────────────────────────────────────── #
_status = {
    'is_processing': False,
    'cancel_requested': False,
    'current': 0,
    'total': 0,
    'message': 'Idle',
    'errors': [],
    'last_run': None,
}
_status_lock = threading.Lock()


def update_status(**kwargs):
    with _status_lock:
        _status.update(kwargs)


def is_cancel_requested() -> bool:
    with _status_lock:
        return _status.get('cancel_requested', False)


# ──────────────────────────────── Routes ────────────────────────────────── #

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    with _status_lock:
        return jsonify(dict(_status))


@app.route('/api/stats')
def get_stats():
    return jsonify(database.get_stats())


@app.route('/api/papers')
def get_papers():
    min_score  = request.args.get('min_score', 1, type=int)
    journal    = request.args.get('journal') or None
    year       = request.args.get('year', type=int) or None
    sort_by    = request.args.get('sort_by', 'interest_score')
    order      = request.args.get('order', 'DESC')
    search     = request.args.get('search') or None
    category   = request.args.get('category') or None
    checked    = request.args.get('checked', type=int) if 'checked' in request.args else None

    papers = database.get_papers(
        min_score=min_score,
        journal=journal,
        year=year,
        sort_by=sort_by,
        order=order,
        search=search,
        category=category,
        checked=checked,
    )
    return jsonify(papers)


@app.route('/api/process', methods=['POST'])
def start_processing():
    with _status_lock:
        if _status['is_processing']:
            return jsonify({'error': 'A fetch is already running.'}), 400

    t = threading.Thread(target=_process_emails_background, daemon=True)
    t.start()
    return jsonify({'message': 'Fetch started.'})


@app.route('/api/cancel', methods=['POST'])
def cancel_processing():
    with _status_lock:
        if not _status['is_processing']:
            return jsonify({'error': 'No fetch is running.'}), 400
        _status['cancel_requested'] = True
    return jsonify({'message': 'Stop requested.'})


# ── Zotero ──────────────────────────────────────────────────────────────── #

def send_paper_to_zotero(paper_id: int) -> dict:
    """논문 하나를 Zotero로 보냄. {'zotero_key', 'existing', 'filled'}를 돌려줌.

    DOI가 없으면 보내기 전에 Crossref/OpenAlex로 찾아 DB에도 채운다.
    Zotero에 이미 있으면(DOI 또는 제목) 새로 만들지 않고, 설정에 따라 빈 서지 칸만 채운다.
    """
    paper = database.get_paper_by_id(paper_id)
    if paper is None:
        raise ValueError('Paper not found.')
    if paper.get('added_to_zotero') and paper.get('zotero_key'):
        return {'zotero_key': paper['zotero_key'], 'existing': True, 'filled': []}
    if not paper.get('doi'):
        found = enrich.enrich(paper)
        if found.get('doi'):
            database.update_paper_metadata(paper_id, found.get('doi'), found.get('abstract'),
                                           found.get('year'))
            paper = database.get_paper_by_id(paper_id)

    # 이미 Zotero에 있는지 확인 (목록이 아직 없으면 백그라운드로 만들기 시작하고 이번에는 확인 없이 보냄)
    if zotero_index.is_built():
        zotero_index.refresh_if_stale()
        existing = zotero_index.find(paper)
    else:
        if not zotero_index.status['running']:
            zotero_index.sync_in_background()
        existing = None

    if existing:
        filled = []
        if database.get_settings()['zotero_existing'] == 'fill':
            filled = zotero_client.fill_missing(existing, paper)
        database.mark_paper_in_zotero(paper_id, existing)
        return {'zotero_key': existing, 'existing': True, 'filled': filled}

    key = zotero_client.add_paper(paper)
    zotero_index.add(key, paper)
    database.mark_paper_in_zotero(paper_id, key)
    return {'zotero_key': key, 'existing': False, 'filled': []}


@app.route('/api/zotero/index', methods=['GET'])
def get_zotero_index():
    return jsonify(zotero_index.info())


@app.route('/api/zotero/index/sync', methods=['POST'])
def post_zotero_index_sync():
    if not zotero_index.status['running']:
        zotero_index.sync_in_background(force_full=bool((request.json or {}).get('full')))
    return jsonify(zotero_index.info())


@app.route('/api/zotero/open/<key>', methods=['POST'])
def open_in_zotero(key):
    """Zotero 데스크톱 앱에서 해당 항목을 선택해 보여 줌 (zotero:// 링크를 Windows에 넘김)."""
    if not key.isalnum():
        return jsonify({'error': 'Invalid key.'}), 400
    try:
        os.startfile(f'zotero://select/library/items/{key}')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/papers/<int:paper_id>/zotero', methods=['POST'])
def post_paper_to_zotero(paper_id):
    if database.get_settings()['zotero_enabled'] != 'on':
        return jsonify({'error': 'Zotero is turned off in Settings.'}), 400
    try:
        return jsonify({'success': True, **send_paper_to_zotero(paper_id)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 설정 ─────────────────────────────────────────────────────────────────── #

@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify({'settings': database.get_settings(), 'choices': database.SETTING_CHOICES})


@app.route('/api/settings', methods=['PUT'])
def put_settings():
    try:
        return jsonify({'settings': database.update_settings(request.json or {})})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/pending')
def get_pending():
    """기다리는 메일 수: 기준 날짜를 적용한 수와 적용하지 않은 수."""
    try:
        settings = database.get_settings()
        waiting = len(_pending_email_ids(settings))
        everything = len(_pending_email_ids({**settings, 'start_date': ''}))
        return jsonify({'waiting': waiting, 'all_unread': everything})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 카테고리 관리 ─────────────────────────────────────────────────────────── #

@app.route('/api/categories', methods=['GET'])
def get_categories():
    return jsonify(database.get_categories())


@app.route('/api/categories', methods=['POST'])
def add_category():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Category name is required.'}), 400
    if database.add_category(name):
        return jsonify({'success': True})
    return jsonify({'error': 'This category already exists.'}), 400


@app.route('/api/categories/<path:name>', methods=['DELETE'])
def delete_category(name):
    database.delete_category(name)
    return jsonify({'success': True})


# ── 논문 수정 ─────────────────────────────────────────────────────────────── #

@app.route('/api/papers/<int:paper_id>/score', methods=['PUT'])
def update_score(paper_id):
    data = request.json or {}
    score = data.get('score')
    if score is None:
        return jsonify({'error': 'Score is required.'}), 400
    try:
        database.update_paper_score(paper_id, score)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/papers/<int:paper_id>/checked', methods=['PUT'])
def update_checked(paper_id):
    data = request.json or {}
    checked = data.get('checked')
    if checked is None:
        return jsonify({'error': 'Read status is required.'}), 400
    try:
        database.update_paper_checked(paper_id, checked)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/papers/<int:paper_id>/categories', methods=['PUT'])
def update_categories(paper_id):
    data = request.json or {}
    cats = data.get('categories', [])
    cats_str = ', '.join([c.strip() for c in cats if c.strip()])
    database.update_paper_categories(paper_id, cats_str)
    return jsonify({'success': True})


# ─────────────────────────── Background Worker ──────────────────────────── #

def _process_emails_background():
    update_status(
        is_processing=True,
        cancel_requested=False,
        current=0,
        total=0,
        errors=[],
        message='Getting unread alert emails from Gmail...',
    )

    try:
        # 1단계: ID 목록만 가져옴 (읽음 처리 안함). 설정의 기준 날짜·순서·개수를 적용
        settings = database.get_settings()
        pending = _pending_email_ids(settings)
        size = settings['batch_size']
        email_ids = pending if size == 'all' else pending[:int(size)]
        total = len(email_ids)
        left_after = len(pending) - total     # 이번에 처리하지 않고 남는 메일 수
        update_status(total=total, message=f'Found {len(pending)} unread alert emails; '
                                           f'fetching {total} this time.')

        if total == 0:
            update_status(
                message='No new emails to fetch.',
                is_processing=False,
                last_run=_now(),
            )
            return

        saved_total = 0
        skipped_total = 0
        sent_total = 0
        processed_count = 0
        errors = []

        for i, email_id in enumerate(email_ids):

            # 취소 확인
            if is_cancel_requested():
                remaining = total - i + left_after
                update_status(
                    message=f'Stopped. {processed_count} emails processed, '
                            f'{saved_total} papers saved. '
                            f'({remaining} remaining emails will be fetched next time.)',
                    is_processing=False,
                    cancel_requested=False,
                    last_run=_now(),
                    errors=errors,
                )
                return

            # 이미 완전히 처리된 이메일은 건너뜀
            if database.is_email_processed(email_id):
                update_status(current=i + 1)
                continue

            try:
                # 이메일 내용 가져오기
                update_status(
                    current=i + 1,
                    message=f'Loading email ({i+1}/{total})...',
                )
                email = gmail_client.get_email_content_by_id(email_id)

                subj = email.get('subject', '(no subject)')[:60]
                update_status(message=f'Analyzing ({i+1}/{total}): {subj}')

                # 논문 목록 추출 → DOI·초록 보강 → 이미 있는 논문 건너뛰기 → 평가
                papers, skipped = paper_processor.process_email(email)
                skipped_total += skipped

                # DB 저장
                saved = 0
                new_ids = []
                for p in papers:
                    paper_id = database.save_paper(p)
                    if paper_id:
                        saved += 1
                        new_ids.append((paper_id, p.get('interest_score') or 0))

                # 설정한 점수 이상이면 Zotero로 자동 보내기 (실패해도 메일 처리는 계속)
                settings_now = database.get_settings()
                min_score = settings_now['zotero_auto_min_score']
                if settings_now['zotero_enabled'] == 'on' and min_score != 'off':
                    for paper_id, score in new_ids:
                        if score >= int(min_score):
                            try:
                                send_paper_to_zotero(paper_id)
                                sent_total += 1
                            except Exception as e:
                                errors.append(f'Zotero send failed (paper {paper_id}): {e}')

                # 성공 후 읽음 처리 + 처리 완료 기록
                gmail_client.mark_email_read(email_id)
                database.mark_email_processed(email_id, len(papers) + skipped)

                saved_total += saved
                processed_count += 1

            except Exception as e:
                err_msg = f"Error in email {i+1}/{total}: {e}"
                errors.append(err_msg)
                print(err_msg)

        update_status(
            message=f'Done. {processed_count} emails processed, {saved_total} papers saved '
                    f'({skipped_total} already in the library were skipped).'
                    + (f' {sent_total} sent to Zotero.' if sent_total else '')
                    + (f' {left_after} emails are still waiting.' if left_after else ''),
            is_processing=False,
            errors=errors,
            last_run=_now(),
        )

    except Exception as e:
        update_status(
            message=f'Error: {e}',
            is_processing=False,
            cancel_requested=False,
            errors=[str(e)],
            last_run=_now(),
        )


def _pending_email_ids(settings: dict) -> list[str]:
    """처리할 차례인 메일 ID: 기준 날짜 이후의 안 읽은 알림 메일 중 아직 처리하지 않은 것.

    Gmail은 최신 메일부터 돌려주므로, 'oldest' 설정이면 순서를 뒤집는다.
    """
    done = database.processed_email_ids()
    ids = [i for i in gmail_client.list_unread_email_ids(settings['start_date']) if i not in done]
    return ids[::-1] if settings['fetch_order'] == 'oldest' else ids


def _now() -> str:
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ──────────────────────────────── Startup ───────────────────────────────── #

def _open_browser():
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:5000')


if __name__ == '__main__':
    print("=" * 55)
    print("  PaperAlert - 학술 논문 알림 처리 시스템")
    print("=" * 55)

    print("\n[1/2] Gmail 인증 확인 중...")
    try:
        gmail_client.get_gmail_service()
        print("  Gmail 인증 완료")
    except Exception as e:
        print(f"  Gmail 인증 실패: {e}")
        sys.exit(1)

    print("[2/2] 웹 서버 시작 중...")

    t = threading.Thread(target=_open_browser, daemon=True)
    t.start()

    print("  http://127.0.0.1:5000 에서 실행 중")
    print("  (종료: Ctrl+C)\n")

    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
