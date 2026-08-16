@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0portable\Test-Portable.ps1" -Root "%~dp0"
set "code=%errorlevel%"
pause
exit /b %code%
