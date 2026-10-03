"""Gmail API 클라이언트 모듈"""
import os
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
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
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
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
                    soup = BeautifulSoup(html, 'lxml')
                    html_body = soup.get_text(separator='\n', strip=True)
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
                soup = BeautifulSoup(raw, 'lxml')
                body = soup.get_text(separator='\n', strip=True)
            else:
                body = raw

    import re
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
            f"Gmail 라벨 '{GMAIL_LABEL}'을 찾을 수 없습니다. "
            "Gmail에서 해당 라벨을 먼저 생성해주세요."
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


# 하위 호환성 유지 (기존 코드에서 호출할 경우 대비)
def fetch_unread_emails(mark_as_read: bool = True) -> list[dict]:
    """미읽은 이메일을 가져옴 (기존 방식)."""
    service = get_gmail_service()
    label_id = get_label_id(service, GMAIL_LABEL)

    if not label_id:
        raise ValueError(
            f"Gmail 라벨 '{GMAIL_LABEL}'을 찾을 수 없습니다."
        )

    results = service.users().messages().list(
        userId='me',
        labelIds=[label_id, 'UNREAD'],
        maxResults=50,
    ).execute()

    messages = results.get('messages', [])
    emails = []

    for msg in messages:
        try:
            email = get_email_content(service, msg['id'])
            emails.append(email)
            if mark_as_read:
                service.users().messages().modify(
                    userId='me',
                    id=msg['id'],
                    body={'removeLabelIds': ['UNREAD']},
                ).execute()
        except Exception as e:
            print(f"이메일 {msg['id']} 가져오기 실패: {e}")

    return emails
