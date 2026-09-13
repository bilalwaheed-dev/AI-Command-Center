@echo off
echo ===================================================
echo Starting AI Command Center Supervisor...
echo ===================================================
cd /d "%~dp0"
python supervisor.py --host 127.0.0.1 --port 5050
pause
