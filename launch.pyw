"""PaperAlert 런처 — pywebview 앱 창 (콘솔 없음, PaperAlert 아이콘)

바로가기는 venv의 Scripts\\pythonw.exe가 아니라 기반 파이썬의 pythonw.exe로
이 파일을 실행한다(create_shortcut.py 참고). uv가 만든 venv의 pythonw.exe는
콘솔용 실행 파일이라 터미널 창을 띄우기 때문이다. 대신 여기서 venv의
site-packages를 직접 불러온다.
"""
import sys
import os
import site
import threading
import time

APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

# ── venv 패키지 불러오기 (기반 pythonw로 실행된 경우) ─────────────────── #
_VENV_SITE = os.path.join(APP_DIR, '.venv', 'Lib', 'site-packages')
if os.path.isdir(_VENV_SITE) and os.path.normcase(sys.prefix) != os.path.normcase(
        os.path.join(APP_DIR, '.venv')):
    site.addsitedir(_VENV_SITE)

APP_ID = 'PaperAlert.App.1'   # create_shortcut.py의 바로가기 AppUserModelID와 같아야 함

# ── 중복 실행 방지: 이미 떠 있으면 그 창을 앞으로 가져오고 끝냄 ───────── #
try:
    import ctypes
    _k32 = ctypes.windll.kernel32
    _mutex = _k32.CreateMutexW(None, False, 'Local\\PaperAlert.SingleInstance')
    if _k32.GetLastError() == 183:            # ERROR_ALREADY_EXISTS
        import ctypes.wintypes as _wt
        _u32 = ctypes.windll.user32

        def _raise_cb(hwnd, _):
            # 트레이 아이콘의 숨은 창은 건너뛰고 pywebview(WinForms) 창만 고름
            title = ctypes.create_unicode_buffer(64)
            cls = ctypes.create_unicode_buffer(64)
            _u32.GetWindowTextW(hwnd, title, 64)
            _u32.GetClassNameW(hwnd, cls, 64)
            if title.value == 'PaperAlert' and cls.value.startswith('WindowsForms'):
                _u32.ShowWindow(hwnd, 9)      # SW_RESTORE
                _u32.SetForegroundWindow(hwnd)
                return False
            return True

        _u32.EnumWindows(ctypes.WINFUNCTYPE(_wt.BOOL, _wt.HWND, _wt.LPARAM)(_raise_cb), 0)
        sys.exit(0)
except SystemExit:
    raise
except Exception:
    pass

# ── stdout/stderr 완전 억제 ───────────────────────────────────────────── #
# pythonw에는 콘솔이 없어 print가 실패할 수 있으므로 devnull로 보낸다
_devnull = open(os.devnull, 'w', encoding='utf-8')
sys.stdout = _devnull
sys.stderr = _devnull

# ── 서브프로세스 콘솔 창 전역 차단 ───────────────────────────────────── #
# pythonw.exe에서 실행되는 자식 프로세스(dotnet.exe, pythonnet 등)가
# 빈 콘솔 창을 열지 못하도록 Popen에 CREATE_NO_WINDOW 플래그를 강제 삽입
import subprocess as _sp
_ORIG_POPEN = _sp.Popen.__init__
def _popen_no_win(self, *a, **kw):
    if sys.platform == 'win32':
        flags = kw.get('creationflags', 0)
        # CREATE_NEW_CONSOLE(0x10) 플래그가 없을 때만 CREATE_NO_WINDOW(0x08000000) 추가
        if not (flags & 0x00000010):
            kw['creationflags'] = flags | 0x08000000
    _ORIG_POPEN(self, *a, **kw)
_sp.Popen.__init__ = _popen_no_win

# ── Windows: 작업표시줄 앱 ID ─────────────────────────────────────────── #
# 바로가기(.lnk)에도 같은 ID를 넣어 두어야 바로가기와 앱 창이 한 아이콘으로 묶인다
try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
except Exception:
    pass

APP_URL  = 'http://127.0.0.1:5000'
ICO_PATH = os.path.join(APP_DIR, 'icon.ico')


# ── 아이콘 생성 ────────────────────────────────────────────────────────── #

def _make_icon_image(size=64):
    from PIL import Image, ImageDraw
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    blue, white, light = (37, 99, 235), (255, 255, 255), (147, 197, 253)
    d.ellipse([2, 2, size - 2, size - 2], fill=blue)
    s = size / 64
    lx, ty = int(18 * s), int(13 * s)
    rw, dh = int(22 * s), int(30 * s)
    corner = int(7 * s)
    d.polygon([
        (lx, ty), (lx + rw - corner, ty), (lx + rw, ty + corner),
        (lx + rw, ty + dh), (lx, ty + dh),
    ], fill=white)
    d.polygon([
        (lx + rw - corner, ty), (lx + rw, ty + corner),
        (lx + rw - corner, ty + corner),
    ], fill=light)
    for i, ly in enumerate([ty + int(10*s), ty + int(16*s), ty + int(22*s)]):
        x2 = lx + rw - (int(8*s) if i == 2 else int(4*s))
        d.rectangle([lx + int(4*s), ly, x2, ly + int(2*s)], fill=blue)
    return img


def _save_ico(path):
    sizes = [16, 32, 48, 64, 128, 256]
    images = [_make_icon_image(s) for s in sizes]
    images[0].save(path, format='ICO', sizes=[(s, s) for s in sizes],
                   append_images=images[1:])


# ── Flask 서버 (백그라운드 스레드) ─────────────────────────────────────── #

def _start_server():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(APP_DIR, '.env'), override=True)

        import logging
        # werkzeug/Flask 로그 완전 억제 (콘솔 출력 방지)
        logging.getLogger('werkzeug').disabled = True
        logging.getLogger('flask').disabled = True

        import database
        import app as flask_app

        database.init_db()
        # Gmail 인증은 여기서 하지 않음 — "새 이메일 처리" 클릭 시 자동 처리
        # 127.0.0.1: 이 컴퓨터에서만 접속 가능 (같은 네트워크의 다른 기기 차단)
        flask_app.app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
    except Exception:
        import traceback
        with open(os.path.join(APP_DIR, 'launch_error.log'), 'w', encoding='utf-8') as f:
            f.write(traceback.format_exc())

threading.Thread(target=_start_server, daemon=True).start()


# ── 로딩 스플래시 HTML (서버 준비될 때까지 표시) ───────────────────────── #
# fetch('/')로 Flask 준비 여부를 주기적으로 확인하고, 준비되면 자동 이동

# 스플래시: 순수 CSS 애니메이션만 사용 (JS fetch 없음 — CORS 문제 방지)
# URL 전환은 Python 쪽에서 window.load_url()로 처리
SPLASH_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body {
  background: #1a3a5c;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  font-family: -apple-system, 'Malgun Gothic', sans-serif;
  gap: 20px;
}
.logo { font-size: 3.5rem; line-height: 1; }
.title { color: #60a5fa; font-size: 2rem; font-weight: 800; letter-spacing: -0.5px; }
.status { color: #93c5fd; font-size: 0.95rem; display: flex; align-items: center; gap: 8px; }
.spinner {
  width: 18px; height: 18px;
  border: 2.5px solid rgba(147,197,253,0.3);
  border-top-color: #60a5fa;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
  <div class="logo">📚</div>
  <div class="title">PaperAlert</div>
  <div class="status">
    <div class="spinner"></div>
    <span>시작 중...</span>
  </div>
</body>
</html>"""


# ── 시스템 트레이 (백그라운드 스레드) ─────────────────────────────────── #

import pystray

def _show_window(icon=None, item=None):
    try:
        import webview
        if webview.windows:
            webview.windows[0].show()
            webview.windows[0].restore()
    except Exception:
        pass

def _quit(icon, item):
    icon.stop()
    os._exit(0)

if not os.path.exists(ICO_PATH):
    _save_ico(ICO_PATH)

from PIL import Image as _Image
try:
    _tray_img = _Image.open(ICO_PATH)
    _tray_img.size = (64, 64)        # ICO에 든 여러 크기 중 64px을 고름
    _tray_img = _tray_img.convert('RGBA')
except Exception:
    _tray_img = _make_icon_image(64)

tray = pystray.Icon(
    name='PaperAlert',
    icon=_tray_img,
    title='PaperAlert',
    menu=pystray.Menu(
        pystray.MenuItem('PaperAlert 열기', _show_window, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('종료', _quit),
    ),
)
tray.run_detached()


# ── pywebview 창 (메인 스레드) ─────────────────────────────────────────── #

import webview
import urllib.request

window = webview.create_window(
    title='PaperAlert',
    html=SPLASH_HTML,      # 스플래시 즉시 표시
    width=1280,
    height=860,
    min_size=(960, 600),
)

def _on_shown():
    """창이 뜬 직후 Python에서 서버 준비를 감지해 URL 전환 (CORS 우회)."""
    def _wait_and_load():
        for _ in range(120):          # 최대 60초 대기
            try:
                urllib.request.urlopen(APP_URL, timeout=1)
                window.load_url(APP_URL)  # 서버 준비 완료 → 앱으로 전환
                return
            except Exception:
                time.sleep(0.5)
    threading.Thread(target=_wait_and_load, daemon=True).start()

webview.start(func=_on_shown, icon=ICO_PATH, debug=False)

# 창 닫히면 앱 전체 종료
tray.stop()
os._exit(0)
