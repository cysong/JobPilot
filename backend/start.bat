@echo off
echo Starting JobPilot Backend...
echo.
echo Make sure you have:
echo - PostgreSQL running on localhost:5432
echo - Redis running on localhost:6379
echo - Updated .env file with correct credentials
echo.
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
