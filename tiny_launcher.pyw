"""PaperAlert 중간 런처 — SW_HIDE STARTUPINFO로 launch.pyw 실행.
이 파일이 STARTUPINFO.wShowWindow=0 을 넘겨줘야 AllocConsole()이 숨겨진
콘솔 창을 만들어 사용자에게 보이지 않는다."""
import subprocess, os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHONW = os.path.join(APP_DIR, '.venv', 'Scripts', 'pythonw.exe')
LAUNCH  = os.path.join(APP_DIR, 'launch.pyw')

si = subprocess.STARTUPINFO()
si.dwFlags    = subprocess.STARTF_USESHOWWINDOW
si.wShowWindow = 0          # SW_HIDE — 자식 프로세스의 AllocConsole 창도 숨겨짐

subprocess.Popen([PYTHONW, LAUNCH], startupinfo=si, cwd=APP_DIR)
# 이 런처는 즉시 종료, launch.pyw가 독립적으로 실행됨
