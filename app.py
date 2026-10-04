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
import gmail_client
import paper_processor

app = Flask(__name__)
database.init_db()

# ── 처리 상태 ─────────────────────────────────────────────────────────── #
_status = {
    'is_processing': False,
    'cancel_requested': False,
    'current': 0,
    'total': 0,
    'message': '대기 중',
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
            return jsonify({'error': '이미 처리 중입니다.'}), 400

    t = threading.Thread(target=_process_emails_background, daemon=True)
    t.start()
    return jsonify({'message': '이메일 처리를 시작합니다.'})


@app.route('/api/cancel', methods=['POST'])
def cancel_processing():
    with _status_lock:
        if not _status['is_processing']:
            return jsonify({'error': '처리 중이 아닙니다.'}), 400
        _status['cancel_requested'] = True
    return jsonify({'message': '취소 요청이 접수되었습니다.'})


# ── 카테고리 관리 ─────────────────────────────────────────────────────────── #

@app.route('/api/categories', methods=['GET'])
def get_categories():
    return jsonify(database.get_categories())


@app.route('/api/categories', methods=['POST'])
def add_category():
    data = request.json or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': '카테고리 이름이 필요합니다.'}), 400
    if database.add_category(name):
        return jsonify({'success': True})
    return jsonify({'error': '이미 존재하는 카테고리입니다.'}), 400


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
        return jsonify({'error': '점수가 필요합니다.'}), 400
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
        return jsonify({'error': '확인 여부가 필요합니다.'}), 400
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
        message='Gmail에서 미읽은 이메일 목록을 가져오는 중...',
    )

    try:
        # 1단계: ID 목록만 가져옴 (읽음 처리 안함)
        email_ids = gmail_client.list_unread_email_ids()
        total = len(email_ids)
        update_status(total=total, message=f'{total}개의 미읽은 이메일을 찾았습니다.')

        if total == 0:
            update_status(
                message='처리할 새 이메일이 없습니다.',
                is_processing=False,
                last_run=_now(),
            )
            return

        saved_total = 0
        skipped_total = 0
        processed_count = 0
        errors = []

        for i, email_id in enumerate(email_ids):

            # 취소 확인
            if is_cancel_requested():
                remaining = total - i
                update_status(
                    message=f'취소됨. {processed_count}개 이메일 처리, '
                            f'{saved_total}편 논문 저장. '
                            f'(미처리 {remaining}개는 다음 실행 시 처리됩니다)',
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
                    message=f'이메일 내용 로드 중 ({i+1}/{total})...',
                )
                email = gmail_client.get_email_content_by_id(email_id)

                subj = email.get('subject', '(제목 없음)')[:60]
                update_status(message=f'분석 중 ({i+1}/{total}): {subj}')

                # 논문 목록 추출 → DOI·초록 보강 → 이미 있는 논문 건너뛰기 → 평가
                papers, skipped = paper_processor.process_email(email)
                skipped_total += skipped

                # DB 저장
                saved = 0
                for p in papers:
                    if database.save_paper(p):
                        saved += 1

                # 성공 후 읽음 처리 + 처리 완료 기록
                gmail_client.mark_email_read(email_id)
                database.mark_email_processed(email_id, len(papers) + skipped)

                saved_total += saved
                processed_count += 1

            except Exception as e:
                err_msg = f"이메일 처리 오류 ({i+1}/{total}): {e}"
                errors.append(err_msg)
                print(err_msg)

        update_status(
            message=f'완료! {processed_count}개 이메일 처리, 논문 {saved_total}편 저장 '
                    f'(이미 있던 논문 {skipped_total}편은 건너뜀).',
            is_processing=False,
            errors=errors,
            last_run=_now(),
        )

    except Exception as e:
        update_status(
            message=f'오류 발생: {e}',
            is_processing=False,
            cancel_requested=False,
            errors=[str(e)],
            last_run=_now(),
        )


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
