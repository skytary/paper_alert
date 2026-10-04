"""Gmail API 클라이언트 모듈"""
import os
import re
import base64
from urllib.parse import urlparse, parse_qs
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CREDENTIALS_PATH = 'credentials.json'
TOKEN_PATH = 'token.json'
GMAIL_LABEL = '논문_알리미'

# 서비스 인스턴스 캐시 (재인증 방지)
_service_cache = None


def get_gmail_service():
    """인증된 Gmail 서비스 객체를 반환. 필요하면 OAuth 플로우 실행."""
    global _service_cache
    if _service_cache:
        return _service_cache

    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        refreshed = False
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                refreshed = True
            except RefreshError:
                # 오래 안 쓰거나 권한이 취소돼 갱신 토큰이 만료됨 → 다시 로그인
                refreshed = False
        if not refreshed:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as f:
            f.write(creds.to_json())

    _service_cache = build('gmail', 'v1', credentials=creds)
    return _service_cache


def get_label_id(service, label_name: str) -> str | None:
    """라벨 이름으로 ID를 검색."""
    results = service.users().labels().list(userId='me').execute()
    for label in results.get('labels', []):
        if label['name'] == label_name:
            return label['id']
    return None


def _unwrap_url(url: str) -> str:
    """Google Scholar 알림의 우회 주소(scholar_url?url=...)를 원래 논문 주소로 풂."""
    parsed = urlparse(url)
    if 'scholar.google.' in parsed.netloc and parsed.path.startswith('/scholar_url'):
        real = parse_qs(parsed.query).get('url')
        if real:
            return real[0]
    return url


def _html_to_text(html: str) -> str:
    """HTML을 글자로 바꾸되, 논문 제목처럼 긴 글자에 걸린 링크는 주소를 남김."""
    soup = BeautifulSoup(html, 'lxml')
    for a in soup.find_all('a', href=True):
        text = a.get_text(' ', strip=True)
        href = a['href'].strip()
        # 짧은 링크(구독 해지, 로고 등)는 주소를 버리고 글자만 남김
        if len(text) >= 15 and href.startswith('http'):
            a.replace_with(f'{text} <{_unwrap_url(href)}>')
    return soup.get_text(separator='\n', strip=True)


def extract_body(payload: dict) -> str:
    """이메일 페이로드에서 텍스트 본문을 추출."""
    body = ''

    if 'parts' in payload:
        plain_body = ''
        html_body = ''
        for part in payload['parts']:
            mime = part.get('mimeType', '')
            if mime == 'text/plain':
                data = part['body'].get('data', '')
                if data:
                    plain_body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            elif mime == 'text/html':
                data = part['body'].get('data', '')
                if data:
                    html = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    html_body = _html_to_text(html)
            elif 'parts' in part:
                nested = extract_body(part)
                if nested:
                    html_body = html_body or nested

        body = plain_body or html_body
    else:
        data = payload.get('body', {}).get('data', '')
        if data:
            raw = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            if payload.get('mimeType', '') == 'text/html':
                body = _html_to_text(raw)
            else:
                body = raw

    body = re.sub(r'\n{3,}', '\n\n', body)
    body = re.sub(r' {2,}', ' ', body)
    return body.strip()


def get_email_content(service, msg_id: str) -> dict:
    """이메일 ID로 내용을 가져옴."""
    msg = service.users().messages().get(
        userId='me', id=msg_id, format='full'
    ).execute()

    subject = ''
    received_at = ''
    for header in msg['payload'].get('headers', []):
        name = header['name'].lower()
        if name == 'subject':
            subject = header['value']
        elif name == 'date':
            received_at = header['value']

    body = extract_body(msg['payload'])

    return {
        'id': msg_id,
        'subject': subject,
        'received_at': received_at,
        'body': body,
    }


def get_email_content_by_id(email_id: str) -> dict:
    """email_id로 이메일 내용 가져오기 (서비스 자동 생성)."""
    return get_email_content(get_gmail_service(), email_id)


def list_unread_email_ids() -> list[str]:
    """'논문_알리미' 라벨의 미읽은 이메일 ID 목록만 반환 (읽음 처리 안함)."""
    service = get_gmail_service()
    label_id = get_label_id(service, GMAIL_LABEL)

    if not label_id:
        raise ValueError(
            f"Gmail label '{GMAIL_LABEL}' was not found. "
            "Create the label in Gmail first."
        )

    results = service.users().messages().list(
        userId='me',
        labelIds=[label_id, 'UNREAD'],
        maxResults=50,
    ).execute()

    return [msg['id'] for msg in results.get('messages', [])]


def mark_email_read(email_id: str):
    """이메일 한 건을 읽음으로 표시."""
    service = get_gmail_service()
    service.users().messages().modify(
        userId='me',
        id=email_id,
        body={'removeLabelIds': ['UNREAD']},
    ).execute()

