# PaperAlert 빠른 시작

[English](QUICKSTART.md) | **한국어**

아무것도 없는 상태에서 첫 논문을 가져오기까지 단계별로 안내합니다. **45분쯤** 잡으세요. 시간 대부분은 Google Cloud 설정(4단계)에 드는데, 이건 한 번만 하면 됩니다.

막히면 맨 아래 [문제가 생겼을 때](#문제가-생겼을-때)를 먼저 보고, 그래도 안 되면 [이슈를 남겨 주세요](https://github.com/skytary/paper_alert/issues/new/choose).

## 준비물

- Windows 10 또는 11 컴퓨터
- 학술지 알림 메일을 받는 Gmail 계정
- Anthropic API 크레딧을 살 신용카드 (시작은 5달러면 충분합니다. 메일 한 통 처리에 약 0.04달러)
- 선택: Zotero 계정 (논문을 Zotero로 보내려면)

## 1단계. 파이썬 설치

1. https://www.python.org/downloads/windows/ 에서 Python 3.12 이상("Windows installer (64-bit)")을 내려받습니다.
2. 설치 프로그램 첫 화면에서 **"Add python.exe to PATH"를 꼭 체크**하고 "Install Now"를 누릅니다.
3. PowerShell을 열고(시작 메뉴에서 "PowerShell" 검색) 확인합니다.
   ```powershell
   python --version
   ```
   `Python 3.12.x` 이상이 나오면 됩니다.

## 2단계. PaperAlert 내려받기

둘 중 하나를 고릅니다.

- **Git 없이**: https://github.com/skytary/paper_alert 에서 초록색 **Code** 버튼 → **Download ZIP**을 누르고 압축을 풉니다.
- **Git으로**: `git clone https://github.com/skytary/paper_alert.git`

**폴더는 경로가 짧은 곳에 두세요.** 예: `C:\Users\<사용자이름>\Documents\paper_alert`. Windows는 파일 경로를 260자로 제한해서, 폴더가 너무 깊은 곳에 있으면 3단계 설치가 실패할 수 있습니다. Dropbox나 OneDrive 폴더에 두려면 먼저 [자료 위치와 백업](MANUAL.ko.md#10-자료-위치와-백업)을 읽어 보세요.

## 3단계. 패키지 설치

PowerShell에서 폴더로 이동해 실행합니다.

```powershell
cd C:\Users\<사용자이름>\Documents\paper_alert
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

몇 분 걸립니다. 빨간 오류 없이 명령 프롬프트가 다시 나오면 끝입니다.

## 4단계. Gmail 읽기 권한 받기 (Google Cloud)

Google은 Gmail을 읽는 모든 앱이 등록돼 있어야 허용합니다. 무료 Google Cloud 프로젝트에 나만 쓰는 PaperAlert를 등록하는 과정입니다. 읽으려는 Gmail과 **같은 Google 계정**으로 진행하세요.

### 4.1 프로젝트 만들기

1. https://console.cloud.google.com 에 로그인합니다. 약관 동의가 나오면 동의합니다.
2. 화면 위쪽의 프로젝트 선택 메뉴 → **새 프로젝트(New project)**.
3. 이름을 `PaperAlert`로 하고 **만들기(Create)**. 화면 위쪽에 새 프로젝트가 선택돼 있는지 확인합니다.

### 4.2 Gmail API 켜기

1. https://console.cloud.google.com/apis/library/gmail.googleapis.com 을 엽니다(위쪽 검색창에서 "Gmail API"를 검색해도 됩니다).
2. **사용(Enable)**을 누릅니다.

### 4.3 동의 화면 설정

1. 메뉴(☰) → **Google 인증 플랫폼(Google Auth platform)** → **브랜딩(Branding)**. **시작하기(Get started)**가 보이면 누릅니다.
2. **앱 정보**: 앱 이름 `PaperAlert`, 사용자 지원 이메일은 내 Gmail 주소. **다음**.
3. **대상(Audience)**: **외부(External)**를 고릅니다(개인 Gmail 계정은 내부(Internal)를 고를 수 없습니다). **다음**.
4. **연락처 정보**: 내 Gmail 주소. **다음**.
5. Google API 서비스 사용자 데이터 정책에 동의하고 **계속**, **만들기**.

### 4.4 나를 테스트 사용자로 추가

1. **Google 인증 플랫폼**에서 **대상(Audience)**을 엽니다.
2. **테스트 사용자(Test users)**에서 **사용자 추가(Add users)**를 누르고 내 Gmail 주소를 넣어 저장합니다.

이 단계를 빠뜨리면 나중에 로그인할 때 "액세스 차단됨(Access blocked)"이나 `access_denied`가 나옵니다.

### 4.5 인증 파일 만들기

1. **Google 인증 플랫폼**에서 **클라이언트(Clients)** → **클라이언트 만들기(Create client)**.
2. 애플리케이션 유형: **데스크톱 앱(Desktop app)**. 이름: `PaperAlert desktop`. **만들기**.
3. 대화상자에서 **JSON 다운로드**를 누릅니다(새 클라이언트 옆의 다운로드 아이콘도 됩니다).
4. 내려받은 파일 이름을 `credentials.json`으로 바꿔 PaperAlert 폴더로 옮깁니다.

> Windows는 파일 확장자를 숨길 수 있습니다. 이름을 `credentials.json`으로 바꿨는데 안 되면, 파일 탐색기 **보기** 메뉴에서 "파일 확장명"을 켜고 이름이 `credentials.json.json`이 아닌지 확인하세요.

### 4.6 (선택) 매주 다시 로그인하지 않게 하기

앱이 "테스트" 상태인 동안 Google은 7일마다 PaperAlert의 권한을 끊어서, 다음 Fetch 때 로그인 창이 다시 뜹니다. 이를 피하려면 **Google 인증 플랫폼** → **대상(Audience)** → **앱 게시(Publish app)**를 누르세요. Google의 검증을 받지 않은 앱이라 로그인 화면에 "Google에서 확인하지 않은 앱"이 나옵니다. **고급** → **PaperAlert(으)로 이동(안전하지 않음)**을 누르면 됩니다. 내 컴퓨터에서 나만 쓰는 내 앱이라 괜찮습니다.

## 5단계. Gmail에서 알림 메일에 라벨 붙이기

PaperAlert는 `논문_알리미` 라벨이 붙은 **안 읽은 메일**만 읽습니다.

1. Gmail에서 라벨을 만듭니다: 왼쪽 메뉴 → **라벨** 옆 **+** → `논문_알리미`.
2. 라벨이 자동으로 붙도록 필터를 만듭니다. Gmail 검색창의 검색 옵션 아이콘을 누르고 **보낸사람**에 알림 발신 주소를 넣습니다. 예:
   `scholaralerts-noreply@google.com OR alerts@sagepub.com OR onlinelibrary@wiley.com`
   **필터 만들기** → **라벨 적용: 논문_알리미**를 체크하고, 이미 받은 메일에도 붙이려면 **일치하는 대화에도 필터 적용**을 체크합니다.
3. 학술지 웹사이트에서 목차(TOC)·OnlineFirst 알림을, Google Scholar에서 알림을 신청합니다. 알림이 오면 보낸 주소를 확인해 필터에 추가합니다.

라벨 이름을 바꾸려면 `gmail_client.py`의 `GMAIL_LABEL`을 고칩니다.

## 6단계. Anthropic API 키 받기

1. https://platform.claude.com 에 가입하거나 로그인합니다.
2. **Settings → Billing → Buy credits**에서 5달러를 충전합니다. 자동 충전(auto-reload)은 꺼 두기를 권합니다.
   > claude.ai 구독과는 **다른 지갑**입니다. claude.ai의 크레딧이나 "extra usage"는 PaperAlert에서 쓸 수 없습니다.
3. **API keys → Create key**. `sk-ant-`로 시작하는 키를 복사해 둡니다. 키는 한 번만 보여 줍니다.

## 7단계. (선택) Zotero API 키 받기

1. https://www.zotero.org/settings/keys 로 갑니다.
2. **Your user ID for use in API calls** 뒤의 숫자를 적어 둡니다.
3. **Create new private key**를 누르고 **Allow library access**와 **Allow write access**를 체크해 저장합니다. 키를 복사합니다.

## 8단계. `.env`에 키 넣기

PaperAlert 폴더에서:

```powershell
copy .env.example .env
notepad .env
```

`ANTHROPIC_API_KEY`를 채우고, Zotero를 쓰면 `ZOTERO_API_KEY`와 `ZOTERO_USER_ID`도 채웁니다. 저장하고 닫습니다. **이 파일은 절대 다른 사람과 공유하지 마세요.**

## 9단계. 연구 관심사 프로필 쓰기

PaperAlert는 내 연구 관심사 프로필에 비춰 논문 점수를 매깁니다.

```powershell
copy research_profile.template.md research_profile.md
notepad research_profile.md
```

`[대괄호]`로 된 자리를 모두 내 관심 주제, 방법, 감점할 분야, 카테고리로 바꿉니다. 구체적으로 쓸수록 점수가 정확해집니다. 완성된 예시는 [examples/research_profile.example.md](examples/research_profile.example.md)에 있습니다(사회계층론·교육사회학 연구자의 프로필). 파일은 언제든 고칠 수 있고, 고친 뒤에 가져오는 논문부터 적용됩니다. 한국어로 써도 됩니다.

## 10단계. PaperAlert 실행

1. 바로가기를 만듭니다.
   ```powershell
   .venv\Scripts\python.exe create_shortcut.py
   ```
2. 폴더의 **PaperAlert**를 더블클릭합니다(시작 메뉴에서 찾아도 됩니다). 앱 창이 열립니다.
3. 처음 Fetch하기 전에 **⚙ Settings**에서 **Emails per fetch**를 **10**으로, **Start date**를 최근 날짜로 정하세요. 첫 시험을 작고 싸게 하기 위해서입니다.
4. **Fetch**를 누릅니다. 브라우저에 Google 로그인 창이 뜹니다. 계정을 고르고, "Google에서 확인하지 않은 앱"이 나오면 **계속**(또는 **고급 → PaperAlert(으)로 이동**)을 누른 뒤 허용합니다.
5. Fetch가 끝나면 논문 목록이 나타납니다. 🎉

다음으로 [사용 매뉴얼](MANUAL.ko.md)에서 필터, Zotero, 배치 처리, 설정 항목을 확인하세요.

## 문제가 생겼을 때

| 보이는 것 | 할 일 |
|---|---|
| `python`을 찾을 수 없다고 나옴 | 파이썬이 PATH에 없습니다. "Add python.exe to PATH"를 체크하고 다시 설치하거나, 3단계에서 `python` 대신 `py`를 쓰세요. |
| 3단계에서 모듈이나 파일이 없다는 오류 | 폴더 경로가 너무 길 수 있습니다. 폴더를 짧은 경로로 옮기고(2단계), `.venv` 폴더를 지운 뒤 3단계를 다시 하세요. |
| 로그인 창에 **액세스 차단됨** 또는 `access_denied` | 내 Gmail 주소를 테스트 사용자로 추가하세요(4.4). 같은 계정으로 로그인했는지도 확인하세요. |
| `redirect_uri_mismatch` | 클라이언트가 데스크톱 앱 유형이 아닙니다. **데스크톱 앱** 유형으로 새 클라이언트를 만들고(4.5) `credentials.json`을 바꾸세요. |
| `credentials.json`을 찾을 수 없음 | PaperAlert 폴더에 파일이 없거나 이름이 다릅니다(4.5). |
| `invalid_grant` | 로그인이 만료됐습니다. 폴더의 `token.json`을 지우고 다시 Fetch하세요. |
| `Gmail label '논문_알리미' was not found` | Gmail에 라벨을 만드세요(5단계). |
| `No new emails to fetch` | Start date 이후에 라벨이 붙은 안 읽은 메일이 없습니다. 필터가 라벨을 붙이는지, 메일이 안 읽음 상태인지 확인하세요. |
| `credit balance is too low` | https://platform.claude.com 에서 크레딧을 충전하세요(6단계). `.env`의 키가 충전한 조직의 키인지도 확인하세요. |
| `authentication_error` 또는 `invalid x-api-key` | `.env`의 Anthropic 키가 틀렸거나 공백이 들어갔습니다. 다시 복사해 넣으세요(6, 8단계). |
| `Research profile not found` 또는 `still contains [placeholders]` | `research_profile.md`를 만들고 채우세요(9단계). |
| 앱 창이 비어 있거나 안 열림 (Windows 10) | Microsoft Edge WebView2 Runtime을 https://developer.microsoft.com/microsoft-edge/webview2/ 에서 설치하고 다시 시도하세요. |
| 앱과 함께 검은 터미널 창이 뜸 | `create_shortcut.py`를 다시 실행하고(10단계) 새 바로가기를 쓰세요. |

그래도 안 되면 [이슈를 남겨 주세요](https://github.com/skytary/paper_alert/issues/new/choose). **Setup help**를 고르고, 화면에 나온 메시지 그대로(캡처도 좋습니다)와 PaperAlert 폴더에 `launch_error.log`가 있으면 그 내용을 함께 적어 주세요. 한국어로 써도 됩니다. **`.env`, `credentials.json`, `token.json`의 내용은 절대 올리지 마세요.**
