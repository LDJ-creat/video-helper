<#
Benchmark closed loop wrapper (Windows).
#>

[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$Profile = "short-local",
    [switch]$SkipStartBackend,
    [string]$DataDir,
    [int]$TimeoutSec = 1200
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot() {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$repoRoot = Get-RepoRoot()
$coreDir = Join-Path $repoRoot "services\core"
if (-not $DataDir) {
    $DataDir = Join-Path $env:TEMP ("vh-benchmark-data-" + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
}
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

$backendProc = $null
try {
    if (-not $SkipStartBackend) {
        $env:DATA_DIR = $DataDir
        $env:WORKER_ENABLE = "1"
        $env:MAX_CONCURRENT_JOBS = "1"
        if (-not $env:TRANSCRIBE_MODEL_SIZE) { $env:TRANSCRIBE_MODEL_SIZE = "tiny" }
        if (-not $env:TRANSCRIBE_DEVICE) { $env:TRANSCRIBE_DEVICE = "cpu" }
        if (-not $env:TRANSCRIBE_COMPUTE_TYPE) { $env:TRANSCRIBE_COMPUTE_TYPE = "int8" }
        $profilesFile = Join-Path $repoRoot "benchmarks\profiles.yaml"
        Push-Location $coreDir
        try {
            $profileEnvJson = uv run python scripts/apply_profile_env.py --profile $Profile --profiles-file $profilesFile 2>$null
        } finally {
            Pop-Location
        }
        if ($profileEnvJson) {
            $overrides = $profileEnvJson | ConvertFrom-Json
            foreach ($prop in $overrides.PSObject.Properties) {
                Set-Item -Path "env:$($prop.Name)" -Value $prop.Value
            }
        }
        $backendProc = Start-Process -FilePath "uv" -ArgumentList @("run", "python", "main.py") -WorkingDirectory $coreDir -PassThru -NoNewWindow
        $deadline = (Get-Date).AddSeconds(60)
        while ((Get-Date) -lt $deadline) {
            try {
                Invoke-RestMethod -Uri "$ApiBaseUrl/api/v1/health" -TimeoutSec 5 | Out-Null
                break
            } catch {
                Start-Sleep -Milliseconds 500
            }
        }
    }

    Push-Location $coreDir
    uv run python scripts/run_benchmark.py `
        --mode benchmark `
        --profile $Profile `
        --api-base $ApiBaseUrl `
        --data-dir $DataDir `
        --profiles-file (Join-Path $repoRoot "benchmarks\profiles.yaml") `
        --out-dir (Join-Path $repoRoot "benchmarks\results")
    Pop-Location
    Write-Host "[ok] benchmark finished profile=$Profile" -ForegroundColor Green
}
finally {
    if ($null -ne $backendProc -and -not $backendProc.HasExited) {
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
}
