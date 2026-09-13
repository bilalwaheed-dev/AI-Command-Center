@echo off
echo ===================================================
echo Starting PC-W1 Worker Daemon (Windows Native)...
echo ===================================================
cd /d "%~dp0"
python worker_daemon.py --server http://127.0.0.1:5050 --worker-id PC-W1 --machine BIG-PC --env WINDOWS-NATIVE
pause
