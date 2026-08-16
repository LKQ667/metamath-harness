@echo off
setlocal
start "" /min powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0portable\Start-Portable.ps1"
exit /b 0
