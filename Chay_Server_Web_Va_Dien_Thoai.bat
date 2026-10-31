@echo off
title GHIEN DOC COMMENT - AI VIDEO MAKER (PC & DIEN THOAI)
echo ======================================================================
echo    DANG KHOI DONG SERVER CHO PHEP KET NOI TU DIEN THOAI VA MAY TINH...
echo ======================================================================
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app_launcher.py
) else (
    python app_launcher.py
)
pause

