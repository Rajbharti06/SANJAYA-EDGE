@echo off
echo ============================================
echo   SANJAYA EDGE - Backend (FastAPI + YOLOv8)
echo ============================================
cd /d "%~dp0backend"
echo Installing requirements...
pip install -r requirements.txt
echo.
echo Starting FastAPI server on http://localhost:8000
echo WebSocket endpoint: ws://localhost:8000/ws/stream/^{video_key^}
echo.
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
