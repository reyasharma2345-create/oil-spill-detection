@echo off
echo =====================================================================
echo   AEGIS-SPILL: AI Maritime Oil Spill Attribution System (PS26143)
echo =====================================================================
echo.
echo Starting Backend FastAPI Server on http://localhost:8000 ...
start "AEGIS-SPILL Backend (Port 8000)" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo Starting Frontend WebGIS Vite Server on http://localhost:5173 ...
start "AEGIS-SPILL Frontend (Port 5173)" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Both services launched!
echo - WebGIS Console: http://localhost:5173
echo - FastAPI Interactive Docs: http://localhost:8000/docs
echo =====================================================================
