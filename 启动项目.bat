@echo off
setlocal

cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\tauri.ps1" dev

if errorlevel 1 (
  echo.
  echo 启动失败，请把上面的错误信息发给 Codex。
  pause
)
