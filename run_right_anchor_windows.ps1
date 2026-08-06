param(
    [Parameter(Mandatory = $true)]
    [string]$MainIp,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPath = Join-Path $projectRoot "backend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Host "Creating backend Python environment..."
    & py -m venv (Join-Path $backendPath ".venv")
    & $pythonPath -m pip install -r (Join-Path $backendPath "requirements.txt")
}

$backendUrl = "http://${MainIp}:5000/api/bluetooth/signals"
if ($WhatIf) {
    Write-Host "ANCHOR_ID=right-anchor"
    Write-Host "BACKEND_URL=$backendUrl"
    Write-Host "Python=$pythonPath"
    exit 0
}

$env:ANCHOR_ID = "right-anchor"
$env:BACKEND_URL = $backendUrl
Set-Location -LiteralPath $backendPath
& $pythonPath ".\scripts\ble_scanner.py"
