<#
Start Video Helper backend (services/core) for local development.

Usage:
  .\scripts\core-dev.ps1
  make core-dev

Equivalent to:
  cd services/core && uv run python main.py
#>

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) { Write-Host "[core-dev] $Message" -ForegroundColor Cyan }

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Require-Command([string]$Name, [string]$Hint) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $cmd) {
        throw "$Name not found. $Hint"
    }
    return $cmd
}

# Ensure WinGet-installed tools (e.g. ffmpeg) are on PATH in fresh shells.
$winGetLinks = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"
if (Test-Path $winGetLinks) {
    $env:PATH = "$winGetLinks;$env:PATH"
}

$repoRoot = Get-RepoRoot
$coreDir = Join-Path $repoRoot "services\core"
$envExample = Join-Path $coreDir ".env.example"
$envFile = Join-Path $coreDir ".env"

Require-Command -Name "uv" -Hint "Install uv: https://docs.astral.sh/uv/getting-started/installation/"

if (-not (Test-Path $coreDir)) {
    throw "Core directory not found: $coreDir"
}

if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Write-Info "No .env found; copy from .env.example first:"
        Write-Host "  Copy-Item `"$envExample`" `"$envFile`"" -ForegroundColor Yellow
    }
    else {
        Write-Info "No .env found in services/core (optional; settings can come from the UI)."
    }
}

Write-Info "Starting backend at http://127.0.0.1:8000"
Write-Info "Working directory: $coreDir"
Write-Host ""

Push-Location $coreDir
try {
    & uv run python main.py
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
