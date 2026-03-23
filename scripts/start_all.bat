@echo off
REM Start both backend and frontend in separate windows.
REM Run stop_all.bat or close the opened windows to shut down.

set "SCRIPT_DIR=%~dp0"

echo +=======================================+
echo ^|   Defense LLM Console -- Full Stack  ^|
echo +=======================================+
echo ^|  API  --^>  http://localhost:8000      ^|
echo ^|  UI   --^>  http://localhost:5173      ^|
echo +=======================================+
echo.

REM Open API in a new window titled "Defense LLM API"
start "Defense LLM API" cmd /k ""%SCRIPT_DIR%start_api.bat""

REM Brief pause so uvicorn banner prints first
timeout /t 2 /nobreak >nul

REM Open UI in a new window titled "Defense LLM UI"
start "Defense LLM UI" cmd /k ""%SCRIPT_DIR%start_web.bat""

echo Both services are starting in separate windows.
echo Run stop_all.bat to stop them, or close each window manually.
