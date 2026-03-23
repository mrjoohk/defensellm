@echo off
REM Start the Defense LLM FastAPI backend

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"

REM Ensure data dirs exist
if not exist "%PROJECT_ROOT%\data\logs" mkdir "%PROJECT_ROOT%\data\logs"

REM Default paths (can be overridden via env)
if not defined DEFENSE_LLM_DB_PATH    set "DEFENSE_LLM_DB_PATH=%PROJECT_ROOT%\data\defense.db"
if not defined DEFENSE_LLM_INDEX_PATH set "DEFENSE_LLM_INDEX_PATH=%PROJECT_ROOT%\data\index"
if not defined DEFENSE_LLM_LOG_PATH   set "DEFENSE_LLM_LOG_PATH=%PROJECT_ROOT%\data\logs"

echo Starting Defense LLM API on http://localhost:8000
echo   DB:    %DEFENSE_LLM_DB_PATH%
echo   Index: %DEFENSE_LLM_INDEX_PATH%
echo.

cd /d "%PROJECT_ROOT%"

REM Use conda env python if available, otherwise fall back to system python
set "PYTHON=C:\Users\user\anaconda3\envs\dllm\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" -m uvicorn src.defense_llm.api.main:app --host 0.0.0.0 --port 8000 --reload
