@echo off
REM Starts CreatorOS in 24/7 mode (scheduler + Telegram bot + dashboard at http://localhost:8787)
cd /d "%~dp0"
python -m creatoros run
pause
