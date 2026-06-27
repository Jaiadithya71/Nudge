@echo off
cd /d "%~dp0"
if exist ..\venv\Scripts\python.exe (
    ..\venv\Scripts\python.exe local_sync.py >> sync.log 2>&1
) else if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe local_sync.py >> sync.log 2>&1
) else (
    python local_sync.py >> sync.log 2>&1
)
