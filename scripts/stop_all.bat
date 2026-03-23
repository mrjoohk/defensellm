@echo off
REM Stop Defense LLM API and UI servers

echo +=======================================+
echo ^|   Defense LLM -- Shutdown Script     ^|
echo +=======================================+

REM 1. Stop API window opened by start_all.bat (title: "Defense LLM API")
echo Stopping API (uvicorn)...
taskkill /F /FI "WINDOWTITLE eq Defense LLM API" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] API window terminated.
) else (
    REM Fallback: kill any python process running uvicorn on port 8000
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
        taskkill /F /PID %%p >nul 2>&1
    )
    echo   [SKIP] API window not found. Attempted port-based kill.
)

REM 2. Stop UI window opened by start_all.bat (title: "Defense LLM UI")
echo Stopping UI (vite)...
taskkill /F /FI "WINDOWTITLE eq Defense LLM UI" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] UI window terminated.
) else (
    REM Fallback: kill any node process on port 5173
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do (
        taskkill /F /PID %%p >nul 2>&1
    )
    echo   [SKIP] UI window not found. Attempted port-based kill.
)

echo.
echo All Defense LLM services have been requested to stop.
pause
