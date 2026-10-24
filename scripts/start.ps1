# PoliBrief V1 - Windows Launcher Script
# Run from the project root: .\scripts\start.ps1
#
# This script:
#   1. Activates the virtual environment
#   2. Starts the FastAPI backend
#   3. Starts the Vite frontend dev server
#   4. Opens the browser
#   5. Waits for Ctrl+C
#   6. Cleans up both processes on exit

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  PoliBrief V1 - Starting Application" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
$VenvPath = Join-Path $ProjectRoot "backend\venv"
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"

if (-not (Test-Path $ActivateScript)) {
    Write-Host "ERROR: Virtual environment not found at $VenvPath" -ForegroundColor Red
    Write-Host "Run: python -m venv backend\venv" -ForegroundColor Yellow
    Write-Host "Then: backend\venv\Scripts\pip install -r backend\requirements.txt" -ForegroundColor Yellow
    exit 1
}

. $ActivateScript
Write-Host "OK - Virtual environment activated" -ForegroundColor Green

# Check .env
$EnvFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Host "WARNING: .env not found. Copying from .env.example" -ForegroundColor Yellow
    Copy-Item (Join-Path $ProjectRoot ".env.example") $EnvFile
    Write-Host "  Please edit .env and set a strong SECRET_KEY before use." -ForegroundColor Yellow
}

# Start Backend
Write-Host ""
Write-Host "Starting backend server..." -ForegroundColor Cyan
$BackendLog = Join-Path $ProjectRoot "storage\logs\backend.log"
New-Item -Path (Split-Path $BackendLog) -ItemType Directory -Force | Out-Null

$BackendProc = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $BackendLog `
    -RedirectStandardError "$BackendLog.err" `
    -PassThru `
    -NoNewWindow

Write-Host "OK - Backend started (PID: $($BackendProc.Id))" -ForegroundColor Green

# Wait for backend to be ready
Write-Host "  Waiting for backend to be ready..." -ForegroundColor Gray
$maxWait = 30
$waited = 0
do {
    Start-Sleep -Seconds 1
    $waited++
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) { break }
    } catch {}
} while ($waited -lt $maxWait)

if ($waited -ge $maxWait) {
    Write-Host "WARNING: Backend did not respond within ${maxWait}s. Check logs at $BackendLog" -ForegroundColor Yellow
} else {
    Write-Host "OK - Backend ready after ${waited}s" -ForegroundColor Green
}

# Start Frontend
Write-Host ""
Write-Host "Starting frontend..." -ForegroundColor Cyan
$FrontendDir = Join-Path $ProjectRoot "frontend"
$FrontendLog = Join-Path $ProjectRoot "storage\logs\frontend.log"

$FrontendProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm.cmd", "run", "dev" `
    -WorkingDirectory $FrontendDir `
    -RedirectStandardOutput $FrontendLog `
    -RedirectStandardError "$FrontendLog.err" `
    -PassThru `
    -NoNewWindow

Write-Host "OK - Frontend started (PID: $($FrontendProc.Id))" -ForegroundColor Green

# Open browser
Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
Write-Host ""
Write-Host "OK - PoliBrief is running!" -ForegroundColor Green
Write-Host "  Backend:  http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  API docs: http://127.0.0.1:8000/api/docs" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Yellow
Write-Host "======================================================" -ForegroundColor Cyan

# Wait and handle Ctrl+C
try {
    while ($true) {
        Start-Sleep -Seconds 2
        if ($BackendProc.HasExited) {
            Write-Host ""
            Write-Host "WARNING: Backend exited unexpectedly (code: $($BackendProc.ExitCode))" -ForegroundColor Red
            Write-Host "Check log: $BackendLog" -ForegroundColor Yellow
            break
        }
    }
} finally {
    Write-Host ""
    Write-Host "Shutting down PoliBrief..." -ForegroundColor Cyan

    # Ctrl+C is delivered to console-attached processes first, giving Uvicorn
    # and Vite a chance to stop cleanly. Kill only process trees rooted at the
    # PIDs created by this launcher if they do not exit in the grace period.
    if (-not $BackendProc.HasExited) {
        $BackendProc.WaitForExit(20000) | Out-Null
    }

    if (-not $FrontendProc.HasExited) {
        & taskkill.exe /PID $FrontendProc.Id /T /F 2>$null | Out-Null
        $FrontendProc.WaitForExit(5000) | Out-Null
        Write-Host "OK - Frontend process tree stopped" -ForegroundColor Green
    }

    if (-not $BackendProc.HasExited) {
        & taskkill.exe /PID $BackendProc.Id /T /F 2>$null | Out-Null
        $BackendProc.WaitForExit(5000) | Out-Null
        Write-Host "OK - Backend process tree stopped" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "PoliBrief stopped. All processes terminated." -ForegroundColor Cyan
    Write-Host ""
}
