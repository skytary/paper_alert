' PaperAlert 무음 런처 — 콘솔 창 없이 실행
' wscript.exe가 이 파일을 실행하면 창이 전혀 나타나지 않음

Dim sh, appDir, pythonw, launchPyw

Set sh = WScript.CreateObject("WScript.Shell")

' 이 VBS 파일이 있는 폴더를 앱 경로로 사용
appDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))

pythonw  = appDir & ".venv\Scripts\pythonw.exe"
launchPyw = appDir & "launch.pyw"

' 창 숨김(0)으로 실행, 완료 대기 안함(False)
sh.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & launchPyw & Chr(34), 0, False

Set sh = Nothing
