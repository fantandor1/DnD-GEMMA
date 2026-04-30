$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "[1/4] Creating virtual environment..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv (Join-Path $projectRoot ".venv")
    }
    else {
        & python -m venv (Join-Path $projectRoot ".venv")
    }
}

Write-Host "[2/4] Checking dependencies..."
& $pythonExe -c "import fastapi, uvicorn, rpg_dm, torch, soundfile, scipy, imageio_ffmpeg; from google import genai" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[3/4] Installing dependencies..."
    & $pythonExe -m pip install -e ".[dev]"
}
else {
    Write-Host "[3/4] Dependencies already installed."
}

if (-not (Test-Path (Join-Path $projectRoot ".env"))) {
    Write-Host "[4/4] Creating .env from template..."
    Copy-Item (Join-Path $projectRoot ".env.example") (Join-Path $projectRoot ".env")
}
else {
    Write-Host "[4/4] Using existing .env"
}

Write-Host "Starting RPG Memory DM on http://127.0.0.1:8008"
Start-Process "http://127.0.0.1:8008"
& $pythonExe -m uvicorn rpg_dm.main:app --reload --host 127.0.0.1 --port 8008
