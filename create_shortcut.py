"""PaperAlert 바로가기 생성 (바탕화면 + 시작 메뉴, 작업표시줄 고정 바로가기가 있으면 갱신).

바로가기 대상은 venv의 Scripts\\pythonw.exe가 아니라 기반 파이썬의 pythonw.exe다.
uv가 만든 venv의 pythonw.exe는 python.exe와 똑같은 콘솔용 실행 파일이라 클릭하면
터미널 창이 함께 뜬다. 기반 pythonw.exe는 GUI용이라 콘솔이 생기지 않고,
venv 패키지는 launch.pyw가 직접 불러온다.

바로가기에는 launch.pyw와 같은 AppUserModelID를 넣는다. 그래야 작업표시줄에서
바로가기 아이콘과 실행 중인 앱 창이 하나로 묶인다.
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(errors='replace')

APP_DIR   = os.path.dirname(os.path.abspath(__file__))
LAUNCH    = os.path.join(APP_DIR, 'launch.pyw')
ICO_PATH  = os.path.join(APP_DIR, 'icon.ico')
APP_ID    = 'PaperAlert.App.1'    # launch.pyw의 APP_ID와 같아야 함

APPDATA   = os.environ['APPDATA']
PINNED    = os.path.join(APPDATA, r'Microsoft\Internet Explorer\Quick Launch\User Pinned'
                                  r'\TaskBar\PaperAlert.lnk')
# 앱 폴더, 시작 메뉴, 작업표시줄 고정 바로가기 (바탕화면에는 만들지 않음)
LNK_PATHS = [
    os.path.join(APP_DIR, 'PaperAlert.lnk'),
    os.path.join(APPDATA, r'Microsoft\Windows\Start Menu\Programs\PaperAlert.lnk'),
]
# 작업표시줄 고정은 프로그램이 대신 할 수 없어서, 이미 고정돼 있을 때만 갱신한다
if os.path.exists(PINNED):
    LNK_PATHS.append(PINNED)


def base_pythonw() -> str:
    """.venv/pyvenv.cfg의 home(기반 파이썬 폴더)에서 pythonw.exe 경로를 찾음."""
    cfg = os.path.join(APP_DIR, '.venv', 'pyvenv.cfg')
    with open(cfg, encoding='utf-8') as f:
        for line in f:
            key, _, value = line.partition('=')
            if key.strip() == 'home':
                path = os.path.join(value.strip(), 'pythonw.exe')
                if os.path.exists(path):
                    return path
    raise FileNotFoundError(f'기반 pythonw.exe를 찾지 못했습니다 ({cfg}의 home 확인)')


# 바로가기를 만들고 System.AppUserModel.ID 속성을 기록하는 PowerShell 스크립트
PS_TEMPLATE = r'''
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class LnkAppId {
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    struct PROPERTYKEY { public Guid fmtid; public uint pid; }
    [StructLayout(LayoutKind.Explicit, Size = 24)]
    struct PROPVARIANT { [FieldOffset(0)] public ushort vt; [FieldOffset(8)] public IntPtr p; }
    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPropertyStore {
        void GetCount(out uint c);
        void GetAt(uint i, out PROPERTYKEY k);
        void GetValue(ref PROPERTYKEY k, out PROPVARIANT v);
        void SetValue(ref PROPERTYKEY k, ref PROPVARIANT v);
        void Commit();
    }
    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    static extern void SHGetPropertyStoreFromParsingName(string path, IntPtr pbc,
        int flags, ref Guid riid, [MarshalAs(UnmanagedType.Interface)] out IPropertyStore ps);
    public static void Set(string lnk, string appId) {
        Guid iid = typeof(IPropertyStore).GUID;
        IPropertyStore ps;
        SHGetPropertyStoreFromParsingName(lnk, IntPtr.Zero, 2, ref iid, out ps); // GPS_READWRITE
        PROPERTYKEY key = new PROPERTYKEY {
            fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), pid = 5 };
        PROPVARIANT v = new PROPVARIANT { vt = 31, p = Marshal.StringToCoTaskMemUni(appId) };
        try { ps.SetValue(ref key, ref v); ps.Commit(); }
        finally { Marshal.FreeCoTaskMem(v.p); Marshal.ReleaseComObject(ps); }
    }
}
"@
$ws = New-Object -ComObject WScript.Shell
foreach ($lnk in @(__LNKS__)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $lnk -Parent) | Out-Null
    $s = $ws.CreateShortcut($lnk)
    $s.TargetPath       = '__TARGET__'
    $s.Arguments        = '"__LAUNCH__"'
    $s.WorkingDirectory = '__APPDIR__'
    $s.IconLocation     = '__ICON__,0'
    $s.Description      = 'PaperAlert - 학술 논문 알림 시스템'
    $s.Save()
    [LnkAppId]::Set($lnk, '__APPID__')
    Write-Output "OK  $lnk"
}
'''


def main():
    target = base_pythonw()

    def q(s):   # PowerShell 작은따옴표 문자열 이스케이프
        return s.replace("'", "''")

    script = (PS_TEMPLATE
              .replace('__LNKS__', ', '.join(f"'{q(p)}'" for p in LNK_PATHS))
              .replace('__TARGET__', q(target))
              .replace('__LAUNCH__', q(LAUNCH))
              .replace('__APPDIR__', q(APP_DIR))
              .replace('__ICON__', q(ICO_PATH))
              .replace('__APPID__', APP_ID))

    # 앱 폴더는 Dropbox 안이라, 막 만든 .lnk를 Dropbox가 잡고 있으면 실패할 수 있어 한 번 더 시도
    for attempt in range(2):
        result = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
        )
        if result.returncode == 0:
            break
        time.sleep(2)
    print(result.stdout.strip())
    if result.returncode != 0:
        print(f'바로가기 생성 실패:\n{result.stderr}')
        return
    print(f'대상: {target}')
    print(f'인수: "{LAUNCH}"')
    print(f'앱 ID: {APP_ID}')
    if not os.path.exists(PINNED):
        print('작업표시줄 고정: 앱을 실행한 뒤 작업표시줄 아이콘을 오른쪽 클릭 → "작업 표시줄에 고정"')


if __name__ == '__main__':
    main()
