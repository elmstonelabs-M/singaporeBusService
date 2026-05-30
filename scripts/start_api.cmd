@echo off
cd /d D:\developwork\singaporeBusService
"C:\Users\devlop\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >> D:\developwork\singaporeBusService\uvicorn.run.log 2>&1
