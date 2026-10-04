# PaperAlert

[English](README.md) | **한국어**

Gmail로 들어오는 학술지 신규 논문 알림(eTOC, OnlineFirst, Google Scholar 알림 등)을 모아서 한 화면에 정리하고, 마음에 드는 논문을 Zotero로 보내는 Windows용 데스크톱 앱입니다.

사용법은 [사용 매뉴얼](MANUAL.ko.md)을 보세요.

## 하는 일

1. Gmail에서 `논문_알리미` 라벨이 붙은 안 읽은 메일을 가져옵니다.
2. Claude API로 메일에 실린 논문 목록을 뽑습니다(서평만 제외).
3. Crossref와 OpenAlex에서 논문마다 DOI와 초록을 찾아 붙이고, 이미 저장된 논문(DOI나 제목이 같은 것)은 건너뜁니다.
4. 새 논문을 사용자의 연구 관심사에 비춰 1~5점으로 평가하고, 요약·데이터·방법·주요 발견을 한국어나 영어로 정리합니다.
5. 결과를 로컬 SQLite DB(`papers.db`)에 저장하고, 점수·학술지·연도·카테고리로 거르고 정렬해 볼 수 있습니다.
6. 논문을 Zotero로 보냅니다. 서지 정보와 요약 메모가 붙고, 이미 Zotero에 있는 논문은 새로 만들지 않습니다. 보낼 컬렉션은 고정 컬렉션, 카테고리별 대응표, 또는 분류 기준 파일을 읽은 Claude의 판단으로 정할 수 있습니다.
7. 밀린 메일이 많을 때는 배치 처리(Message Batches API)로 비용을 절반으로 줄일 수 있습니다.

## 필요한 것

- Windows, Python 3.10 이상
- Anthropic API 키와 크레딧 (https://platform.claude.com)
- Gmail API를 켠 Google Cloud 프로젝트의 OAuth 클라이언트 파일(`credentials.json`, 데스크톱 앱 유형)
- Zotero API 키(쓰기 권한)와 사용자 ID (https://www.zotero.org/settings/keys). Zotero 기능을 쓰지 않으면 필요 없습니다.

## 설치

```powershell
git clone https://github.com/skytary/paper_alert.git
cd paper_alert
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env    # .env를 열어 API 키를 채웁니다
```

그다음:

1. Google Cloud Console에서 내려받은 OAuth 클라이언트 파일을 `credentials.json`이라는 이름으로 이 폴더에 둡니다.
2. Gmail에 `논문_알리미` 라벨을 만들고, 논문 알림 메일에 이 라벨이 자동으로 붙도록 필터를 설정합니다. 라벨 이름을 바꾸려면 `gmail_client.py`의 `GMAIL_LABEL`을 고칩니다.
3. **`paper_processor.py`의 `SYSTEM_PROMPT`를 자기 연구 관심사에 맞게 고칩니다.** 지금 들어 있는 프롬프트는 만든 사람(사회계층론·교육사회학·가족인구학 연구자)의 관심사와 강의 목록을 기준으로 점수를 매기도록 짜여 있습니다. 카테고리 이름을 바꾸면 `database.py`의 `DEFAULT_CATEGORIES`도 같이 바꿉니다.

## 실행

- 바로가기 만들기: `.venv\Scripts\python.exe create_shortcut.py`. 앱 폴더(`PaperAlert.lnk`)와 시작 메뉴에 만들고, 작업표시줄에 고정한 바로가기가 있으면 같이 고칩니다. 작업표시줄 고정은 앱을 실행한 뒤 아이콘을 오른쪽 클릭해 "작업 표시줄에 고정"을 누릅니다. 이후로는 바로가기로 실행합니다.
  - 바로가기는 venv의 `Scripts\pythonw.exe`가 아니라 기반 파이썬의 `pythonw.exe`를 실행합니다. uv로 만든 venv의 `pythonw.exe`는 콘솔용 실행 파일이라 터미널 창이 함께 뜨기 때문입니다. venv 패키지는 `launch.pyw`가 직접 불러옵니다.
  - 바로가기와 앱 창에 같은 앱 ID(`PaperAlert.App.1`)가 붙어 있어 작업표시줄에서 한 아이콘으로 묶입니다. 이미 떠 있을 때 바로가기를 다시 누르면 기존 창이 앞으로 옵니다.
- 브라우저로 실행: `.venv\Scripts\python.exe app.py` 후 http://127.0.0.1:5000

처음 **Fetch**를 누르면 브라우저에서 Google 로그인 창이 뜨고, 승인하면 `token.json`이 생깁니다. 오래 쓰지 않아 인증이 만료됐을 때도 같은 로그인 창이 다시 뜹니다.

화면은 영어입니다. 설정(⚙ Settings)에서 요약 언어, 기준 날짜, 처리 개수와 순서, 배치 처리, Zotero 관련 옵션을 정합니다. 자세한 내용은 [사용 매뉴얼](MANUAL.ko.md)에 있습니다.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `app.py` | Flask 웹앱, 이메일 처리 백그라운드 작업 |
| `gmail_client.py` | Gmail API 인증과 메일 읽기 |
| `paper_processor.py` | Claude API로 논문 추출·점수 매기기 (관심사 프롬프트 포함) |
| `enrich.py` | Crossref·OpenAlex로 DOI·초록 보강 |
| `batch_processor.py` | 배치 처리 (Message Batches API, 반값) |
| `database.py` | SQLite 저장·조회, 설정 |
| `zotero_client.py` | Zotero Web API로 논문 추가, 빈 서지 칸 채우기 |
| `zotero_index.py` | Zotero 라이브러리의 DOI·제목 목록 (이미 있는 논문 확인) |
| `zotero_targets.py` | Zotero로 보낼 컬렉션 정하기 (루트 / 컬렉션 / 카테고리 / 기준 파일) |
| `version.py` | 버전·제작자 정보 (About 창) |
| `templates/index.html` | 화면(단일 페이지) |
| `static/owl.png` | About 창 그림 |
| `launch.pyw` | pywebview 창과 트레이 아이콘으로 앱을 띄우는 런처 |
| `create_shortcut.py` | 앱 폴더·시작 메뉴·작업표시줄 바로가기 생성 |

## 주의

- `.env`, `credentials.json`, `token.json`, `papers.db`에는 개인 키와 자료가 들어가므로 `.gitignore`로 막아 두었습니다. 직접 커밋하지 마세요.
- 서버는 `127.0.0.1:5000`으로 떠서 이 컴퓨터에서만 접속할 수 있습니다. 같은 네트워크의 다른 기기에서 열려면 `app.py`와 `launch.pyw`의 `host`를 `'0.0.0.0'`으로 바꾸세요(인증이 없으니 공용 와이파이에서는 권하지 않습니다).
- Claude 모델(`MODEL`, 기본 `claude-sonnet-5-5`)과 생각 깊이(`EFFORT`, 기본 `medium`)는 `paper_processor.py`에서 바꿀 수 있습니다. 응답 형식은 JSON 스키마(`EXTRACT_SCHEMA`, `SCORE_SCHEMA`)로 고정되고, 관심사 프롬프트는 캐싱됩니다.

Claude Code로 만들었습니다(첫 버전 2026년 3~4월, 2.0 업데이트 2026년 10월).

## 제작자

Seongsoo Choi, Department of Sociology, Yonsei University (s.choi@yonsei.ac.kr)

## 라이선스

MIT License. 자세한 내용은 [LICENSE](LICENSE)를 보세요.
