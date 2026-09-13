@echo off
echo ===================================================
echo Starting AI Command Center Supervisor...
echo ===================================================
cd /d "%~dp0"
python supervisor.py --host 0.0.0.0 --port 5050
pause
