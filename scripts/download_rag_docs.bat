@echo off
REM scripts/download_rag_docs.bat

set "SCRIPT_DIR=%~dp0"

echo Running python downloader script...

set "PYTHON=C:\Users\user\anaconda3\envs\dllm\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" "%SCRIPT_DIR%download_rag_docs.py"
