@echo off
echo Starting JobPilot Backend...
echo.
echo Make sure you have:
echo - PostgreSQL running
echo - Redis running
echo - Updated .env file with correct credentials
echo.
call .venv\Scripts\activate.bat
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
