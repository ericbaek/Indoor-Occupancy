[CmdletBinding()]
param(
    [ValidateSet("Docker", "Native")]
    [string]$Mode = "Docker",
    [switch]$Detached,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Invoke-DockerCommand {
    param([string[]]$Arguments)

    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed: docker $($Arguments -join ' ')"
    }
}

if ($Mode -eq "Docker") {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is not installed or is not available in PATH."
    }

    Set-Location -LiteralPath $projectRoot
    if ($WhatIf) {
        Write-Host "docker compose down"
        Write-Host "docker compose build backend"
        Write-Host "docker compose run --rm --no-deps backend sh -c rm -f -- /app/instance/occupancy.db /app/instance/occupancy.db-shm /app/instance/occupancy.db-wal"
        Write-Host "docker compose up --build$($(if ($Detached) { ' -d' } else { '' }))"
        exit 0
    }

    Invoke-DockerCommand @("compose", "down")
    Invoke-DockerCommand @("compose", "build", "backend")
    Invoke-DockerCommand @(
        "compose", "run", "--rm", "--no-deps", "backend",
        "sh", "-c",
        "rm -f -- /app/instance/occupancy.db /app/instance/occupancy.db-shm /app/instance/occupancy.db-wal"
    )

    $upArguments = @("compose", "up", "--build")
    if ($Detached) {
        $upArguments += "-d"
    }
    Invoke-DockerCommand $upArguments
    exit 0
}

$backendPath = Join-Path $projectRoot "backend"
$instancePath = [System.IO.Path]::GetFullPath((Join-Path $backendPath "instance"))
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"
$databaseFiles = @(
    (Join-Path $instancePath "occupancy.db"),
    (Join-Path $instancePath "occupancy.db-shm"),
    (Join-Path $instancePath "occupancy.db-wal")
)

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Backend environment not found: $pythonPath"
}

foreach ($databaseFile in $databaseFiles) {
    $resolvedTarget = [System.IO.Path]::GetFullPath($databaseFile)
    if (-not $resolvedTarget.StartsWith($instancePath + [System.IO.Path]::DirectorySeparatorChar)) {
        throw "Unsafe database reset target: $resolvedTarget"
    }
    if ($WhatIf) {
        Write-Host "Remove $resolvedTarget"
    }
    elseif (Test-Path -LiteralPath $resolvedTarget) {
        Remove-Item -LiteralPath $resolvedTarget -Force
    }
}

if ($WhatIf) {
    Write-Host "Start backend with DATABASE_PATH=$($databaseFiles[0])"
    exit 0
}

$env:DATABASE_PATH = $databaseFiles[0]
Set-Location -LiteralPath $backendPath
& $pythonPath ".\run.py"
