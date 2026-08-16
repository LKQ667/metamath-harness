@echo off
title MetaMath Harness
cd /d "%~dp0"
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if errorlevel 1 (
  echo.
  echo Install or start failed. Keep this window and report the screenshot.
  pause
)
