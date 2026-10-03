"""Zotero Web API 연동 모듈"""
import os
import requests

ZOTERO_API_BASE = 'https://api.zotero.org'


def add_paper_to_zotero(paper: dict) -> str:
    """논문 정보를 Zotero 라이브러리에 추가하고 item key를 반환."""
    api_key = os.getenv('ZOTERO_API_KEY', '').strip()
    user_id = os.getenv('ZOTERO_USER_ID', '').strip()
    library_type = os.getenv('ZOTERO_LIBRARY_TYPE', 'user').strip()

    if not api_key or not user_id:
        raise ValueError(
            "ZOTERO_API_KEY와 ZOTERO_USER_ID가 .env 파일에 설정되지 않았습니다."
        )

    headers = {
        'Zotero-API-Key': api_key,
        'Zotero-API-Version': '3',
        'Content-Type': 'application/json',
    }

    # Zotero journalArticle 형식 구성
    item = {
        'itemType': 'journalArticle',
        'title': paper.get('title', ''),
        'abstractNote': paper.get('abstract') or '',
        'publicationTitle': paper.get('journal') or '',
        'date': str(paper.get('year', '')) if paper.get('year') else '',
        'DOI': paper.get('doi') or '',
        'creators': _parse_authors(paper.get('authors', '')),
        'tags': [
            {'tag': f'score:{paper.get("interest_score", "")}'},
            {'tag': 'PaperAlert'},
        ],
    }

    if library_type == 'group':
        url = f'{ZOTERO_API_BASE}/groups/{user_id}/items'
    else:
        url = f'{ZOTERO_API_BASE}/users/{user_id}/items'

    response = requests.post(url, json=[item], headers=headers, timeout=15)
    response.raise_for_status()

    result = response.json()
    successful = result.get('successful', {})
    if successful:
        item_key = list(successful.values())[0]['key']
    else:
        failed = result.get('failed', {})
        if failed:
            first_error = list(failed.values())[0]
            raise ValueError(f"Zotero 저장 실패: {first_error.get('message', '알 수 없는 오류')}")
        raise ValueError("Zotero API가 예상치 않은 응답을 반환했습니다.")

    # 평가 이유를 별도 노트 아이템으로 추가
    if paper.get('score_reason'):
        note = {
            'itemType': 'note',
            'parentItem': item_key,
            'note': f'<p><b>관심도 평가 ({paper.get("interest_score")}점):</b><br>{paper["score_reason"]}</p>',
            'tags': [],
        }
        requests.post(url, json=[note], headers=headers, timeout=15)

    return item_key


def _parse_authors(authors_str: str) -> list[dict]:
    """저자 문자열을 Zotero creator 형식으로 변환."""
    if not authors_str:
        return []

    creators = []
    for author in authors_str.split(','):
        author = author.strip()
        if not author:
            continue

        # "LastName FirstName" 또는 "FirstName LastName" 패턴 처리
        parts = author.split()
        if len(parts) >= 2:
            # 마지막 단어를 성(lastName)으로 처리
            creators.append({
                'creatorType': 'author',
                'firstName': ' '.join(parts[:-1]),
                'lastName': parts[-1],
            })
        else:
            creators.append({
                'creatorType': 'author',
                'name': author,
            })

    return creators
