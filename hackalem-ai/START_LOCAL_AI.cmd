@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -X utf8 start_local_ai.py
pause
