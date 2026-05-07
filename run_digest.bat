@echo off
REM Обёртка для Task Scheduler: запускает make_digest.py из venv в директории скрипта
chcp 65001 >nul
cd /d "%~dp0"
"venv\Scripts\python.exe" make_digest.py
exit /b %ERRORLEVEL%
