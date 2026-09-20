@echo off
setlocal
set ROOT=%~dp0..
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
endlocal
