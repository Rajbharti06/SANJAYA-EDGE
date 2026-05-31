@echo off
echo ============================================
echo   SANJAYA EDGE - Frontend (React + Vite)
echo ============================================
cd /d "%~dp0frontend"
echo Installing node modules (first time only)...
npm install
echo.
echo Starting dev server on http://localhost:5173
echo.
npm run dev
pause
