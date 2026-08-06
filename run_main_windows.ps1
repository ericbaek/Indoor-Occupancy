param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPath = Join-Path $projectRoot "backend"
$frontendPath = Join-Path $projectRoot "frontend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Host "Creating backend Python environment..."
    & py -m venv (Join-Path $backendPath ".venv")
    & $pythonPath -m pip install -r (Join-Path $backendPath "requirements.txt")
}

if (-not (Test-Path -LiteralPath (Join-Path $frontendPath "node_modules"))) {
    Write-Host "Installing frontend packages..."
    Push-Location $frontendPath
    try {
        & npm.cmd install
    }
    finally {
        Pop-Location
    }
}

$escapedBackend = $backendPath.Replace("'", "''")
$escapedFrontend = $frontendPath.Replace("'", "''")
$escapedPython = $pythonPath.Replace("'", "''")

$backendCommand = "Set-Location -LiteralPath '$escapedBackend'; & '$escapedPython' '.\run.py'"
$frontendCommand = "Set-Location -LiteralPath '$escapedFrontend'; & npm.cmd run dev -- --host 0.0.0.0"
$scannerCommand = "Set-Location -LiteralPath '$escapedBackend'; `$env:ANCHOR_ID='left-anchor'; `$env:BACKEND_URL='http://127.0.0.1:5000/api/bluetooth/signals'; & '$escapedPython' '.\scripts\ble_scanner.py'"

if ($WhatIf) {
    Write-Host "Backend : $backendCommand"
    Write-Host "Frontend: $frontendCommand"
    Write-Host "Scanner : $scannerCommand"
    exit 0
}

Start-Process powershell.exe -WindowStyle Normal -ArgumentList @("-NoExit", "-Command", $backendCommand)
Start-Process powershell.exe -WindowStyle Normal -ArgumentList @("-NoExit", "-Command", $frontendCommand)
Start-Process powershell.exe -WindowStyle Normal -ArgumentList @("-NoExit", "-Command", $scannerCommand)

Write-Host "Native services started in three PowerShell windows."
Write-Host "Heatmap: http://localhost:5173"
Write-Host "API:     http://localhost:5000/api/bluetooth/signal-strength"
