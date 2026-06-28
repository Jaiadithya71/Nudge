@echo off
cd /d "%~dp0.."
call venv\Scripts\activate.bat
python bot\cloud_bot.py
pause
