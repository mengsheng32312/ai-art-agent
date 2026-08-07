@echo off
setlocal

cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\tauri.ps1" dev

echo.
echo 项目启动进程已退出。如有错误，请把上面的信息发给 Codex。
pause
