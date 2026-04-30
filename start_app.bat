@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [1/4] Creating virtual environment...
    where py >nul 2>nul
    if %errorlevel%==0 (
        py -3 -m venv "%~dp0.venv"
    ) else (
        python -m venv "%~dp0.venv"
    )
    if errorlevel 1 goto :fail
)

echo [2/4] Checking dependencies...
"%PYTHON_EXE%" -c "import fastapi, uvicorn, rpg_dm, torch, soundfile, scipy, imageio_ffmpeg; from google import genai" >nul 2>nul
if errorlevel 1 (
    echo [3/4] Installing dependencies...
    "%PYTHON_EXE%" -m pip install -e .[dev]
    if errorlevel 1 goto :fail
) else (
    echo [3/4] Dependencies already installed.
)

if not exist ".env" (
    echo [4/4] Creating .env from template...
    copy /Y ".env.example" ".env" >nul
) else (
    echo [4/4] Using existing .env
)

echo Starting RPG Memory DM on http://127.0.0.1:8008
start "" "http://127.0.0.1:8008"
"%PYTHON_EXE%" -m uvicorn rpg_dm.main:app --reload --host 127.0.0.1 --port 8008
exit /b %errorlevel%

:fail
echo.
echo Failed to prepare the application.
pause
exit /b 1
