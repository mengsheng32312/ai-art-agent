@echo off
setlocal

cd /d "%~dp0"
cmd.exe /k powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\tauri.ps1" dev
