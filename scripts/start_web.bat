@echo off
REM Start the Defense LLM React frontend dev server

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "WEB_DIR=%PROJECT_ROOT%\web"

cd /d "%WEB_DIR%"

REM Reinstall if node_modules is missing OR was installed on Linux (no win32 esbuild binary)
if not exist "node_modules" goto :do_install
if not exist "node_modules\@esbuild\win32-x64" goto :do_install
goto :skip_install

:do_install
echo Installing npm dependencies (Windows)...
if exist "node_modules" rmdir /s /q "node_modules"
npm install

:skip_install

echo Starting Defense LLM UI on http://localhost:5173
echo (API proxy -^> http://localhost:8000)
echo.
npm run dev
