"""데스크톱에 PaperAlert 바로가기 생성."""
import os
import subprocess

APP_DIR   = os.path.dirname(os.path.abspath(__file__))
PYTHONW   = os.path.join(APP_DIR, '.venv', 'Scripts', 'pythonw.exe')
LAUNCH    = os.path.join(APP_DIR, 'launch.pyw')
ICO_PATH  = os.path.join(APP_DIR, 'icon.ico')
DESKTOP   = os.path.join(os.path.expanduser('~'), 'Desktop')
LNK_PATH  = os.path.join(DESKTOP, 'PaperAlert.lnk')

# ── 아이콘 생성 ────────────────────────────────────────────────────────── #
def ensure_icon():
    if os.path.exists(ICO_PATH):
        return
    try:
        from PIL import Image, ImageDraw
        def make(size):
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            blue, white, light = (37, 99, 235), (255, 255, 255), (147, 197, 253)
            d.ellipse([2, 2, size-2, size-2], fill=blue)
            s = size/64
            lx, ty = int(18*s), int(13*s)
            rw, dh = int(22*s), int(30*s)
            corner = int(7*s)
            d.polygon([(lx,ty),(lx+rw-corner,ty),(lx+rw,ty+corner),(lx+rw,ty+dh),(lx,ty+dh)], fill=white)
            d.polygon([(lx+rw-corner,ty),(lx+rw,ty+corner),(lx+rw-corner,ty+corner)], fill=light)
            for i, ly in enumerate([ty+int(10*s), ty+int(16*s), ty+int(22*s)]):
                x2 = lx+rw-(int(8*s) if i==2 else int(4*s))
                d.rectangle([lx+int(4*s), ly, x2, ly+int(2*s)], fill=blue)
            return img
        sizes = [16, 32, 48, 64, 128, 256]
        imgs = [make(s) for s in sizes]
        imgs[0].save(ICO_PATH, format='ICO', sizes=[(s,s) for s in sizes], append_images=imgs[1:])
        print(f'아이콘 생성: {ICO_PATH}')
    except Exception as e:
        print(f'아이콘 생성 실패: {e}')

ensure_icon()

# ── 바로가기 생성 ──────────────────────────────────────────────────────── #
# pythonw.exe: 콘솔 창 없이 실행 (pywebview가 앱 창을 직접 만듦)
ps_script = f"""
$ws = New-Object -ComObject WScript.Shell
$s  = $ws.CreateShortcut('{LNK_PATH}')
$s.TargetPath       = '{PYTHONW}'
$s.Arguments        = '"{LAUNCH}"'
$s.WorkingDirectory = '{APP_DIR}'
$s.IconLocation     = '{ICO_PATH},0'
$s.Description      = 'PaperAlert - 학술 논문 알림 시스템'
$s.Save()
""".strip()

result = subprocess.run(
    ['powershell', '-NonInteractive', '-Command', ps_script],
    capture_output=True, text=True
)

if result.returncode == 0:
    print(f'바로가기 생성 완료: {LNK_PATH}')
    print(f'  대상: {PYTHONW}')
    print(f'  인수: "{LAUNCH}"')
    print(f'  아이콘: {ICO_PATH}')
else:
    print(f'바로가기 생성 실패:\n{result.stderr}')
