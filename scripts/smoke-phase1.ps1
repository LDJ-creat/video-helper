<#
Phase 1 Smoke Test (Windows PowerShell)

One-click flow:
  1) Start backend (services/core)
  2) Wait for /api/v1/health
  3) Insert a synthetic Job row into SQLite
  4) Write synthetic JSONL logs
  5) curl-verify: SSE, logs, cancel, retry

Usage:
  .\scripts\smoke-phase1.ps1
  .\scripts\smoke-phase1.ps1 -SkipStartBackend
  .\scripts\smoke-phase1.ps1 -ApiBaseUrl "http://127.0.0.1:8000" -TimeoutSec 45
  Set-ExecutionPolicy -Scope Process Bypass -Force; .\\scripts\\smoke-phase1.ps1

Notes:
  - Uses curl.exe (NOT PowerShell's curl alias).
  - Default DATA_DIR is repo-root\data.
#>

[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [int]$TimeoutSec = 30,
    [switch]$SkipStartBackend,
    [string]$DataDir,
    [string]$LogCursorSecret = "dev-log-cursor-secret"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host "[smoke] $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[ok] $Message" -ForegroundColor Green
}

function Write-Fail([string]$Message) {
    Write-Host "[fail] $Message" -ForegroundColor Red
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) {
        throw $Message
    }
}

function Get-RepoRoot() {
    $root = Resolve-Path (Join-Path $PSScriptRoot "..")
    return $root.Path
}

function Invoke-CurlText([string]$Url, [string[]]$CurlArgs = @()) {
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    Assert-True ($null -ne $curl) "curl.exe not found on PATH"

    $allArgs = @("-sS", "--max-time", "10") + $CurlArgs + @($Url)
    $out = & $curl.Source @allArgs
    if ($out -is [System.Array]) {
        $out = ($out -join "`n")
    }
    $exit = $LASTEXITCODE
    Assert-True ($exit -eq 0) "curl failed ($exit): $Url"
    return $out
}

function Invoke-CurlJson([string]$Url, [string[]]$CurlArgs = @()) {
    $text = Invoke-CurlText -Url $Url -CurlArgs $CurlArgs
    try {
        return $text | ConvertFrom-Json
    }
    catch {
        throw "Expected JSON but got: $text"
    }
}

function Wait-ForHealth([string]$HealthUrl, [int]$TimeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-CurlJson -Url $HealthUrl
            if ($resp.status -and $resp.ready -ne $null) {
                return $resp
            }
        }
        catch {
            Start-Sleep -Milliseconds 400
            continue
        }
        Start-Sleep -Milliseconds 400
    }
    throw "Timed out waiting for health: $HealthUrl"
}

$repoRoot = Get-RepoRoot
$coreDir = Join-Path $repoRoot "services\core"

if (-not $DataDir) {
    $DataDir = Join-Path $repoRoot "data"
}

$dataDirResolved = (Resolve-Path -Path $DataDir -ErrorAction SilentlyContinue)
if ($null -eq $dataDirResolved) {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
    $dataDirResolved = Resolve-Path $DataDir
}
$DataDir = $dataDirResolved.Path

$jobsLogsDir = Join-Path $DataDir "logs\jobs"
New-Item -ItemType Directory -Path $jobsLogsDir -Force | Out-Null

$dbPath = Join-Path $DataDir "core.sqlite3"

$jobId = [guid]::NewGuid().ToString()
$projectId = [guid]::NewGuid().ToString()

$backendProc = $null
$backendOut = Join-Path $DataDir "smoke-backend.stdout.log"
$backendErr = Join-Path $DataDir "smoke-backend.stderr.log"

$prevEnv = @{}
foreach ($k in @("DATA_DIR", "LOG_CURSOR_SECRET", "SMOKE_JOB_ID", "SMOKE_PROJECT_ID", "SMOKE_DB_PATH")) {
    $item = Get-Item -Path ("Env:" + $k) -ErrorAction SilentlyContinue
    $prevEnv[$k] = if ($null -ne $item) { $item.Value } else { $null }
}

try {
    Write-Info "Repo root: $repoRoot"
    Write-Info "DATA_DIR: $DataDir"
    Write-Info "DB: $dbPath"
    Write-Info "JobId: $jobId"

    if (-not $SkipStartBackend) {
        Write-Info "Starting backend (services/core)..."

        # PowerShell 5.1 Start-Process doesn't support -Environment; set env vars in-session.
        $env:DATA_DIR = $DataDir
        $env:LOG_CURSOR_SECRET = $LogCursorSecret

        $pythonVenv = Join-Path $coreDir ".venv\Scripts\python.exe"
        if (Test-Path $pythonVenv) {
            Write-Info "Using venv python: $pythonVenv"
            $backendProc = Start-Process -FilePath $pythonVenv -ArgumentList @("main.py") -WorkingDirectory $coreDir -NoNewWindow -PassThru -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr
        }
        else {
            $uv = Get-Command uv -ErrorAction SilentlyContinue
            Assert-True ($null -ne $uv) "Neither services/core/.venv nor uv found. Install uv, or run backend manually and use -SkipStartBackend."
            Write-Info "Using uv run python main.py"
            $backendProc = Start-Process -FilePath $uv.Source -ArgumentList @("run", "python", "main.py") -WorkingDirectory $coreDir -NoNewWindow -PassThru -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr
        }

        Write-Info "Backend PID: $($backendProc.Id)"
    }
    else {
        Write-Info "SkipStartBackend enabled; assuming backend already running."
    }

    $healthUrl = "$ApiBaseUrl/api/v1/health"
    Write-Info "Waiting for health: $healthUrl"
    $health = Wait-ForHealth -HealthUrl $healthUrl -TimeoutSeconds $TimeoutSec
    Write-Ok "Health OK (ready=$($health.ready))"

    # Insert job row into SQLite
    Write-Info "Inserting synthetic job into SQLite..."
    $insertPy = @'
import os, sqlite3, time
job_id = os.environ["SMOKE_JOB_ID"]
project_id = os.environ["SMOKE_PROJECT_ID"]
db_path = os.environ["SMOKE_DB_PATH"]
now_ms = int(time.time() * 1000)
con = sqlite3.connect(db_path)
cur = con.cursor()
cur.execute(
    "INSERT OR REPLACE INTO jobs(job_id, project_id, type, status, stage, progress, error, updated_at_ms) VALUES(?,?,?,?,?,?,?,?)",
    (job_id, project_id, "download", "running", "ingest", None, None, now_ms),
)
con.commit()
con.close()
print(job_id)
'@

    $tmpPyPath = Join-Path $env:TEMP ("smoke_insert_job_{0}.py" -f ([guid]::NewGuid().ToString("N")))
    Set-Content -Path $tmpPyPath -Value $insertPy -Encoding UTF8

    $env:SMOKE_JOB_ID = $jobId
    $env:SMOKE_PROJECT_ID = $projectId
    $env:SMOKE_DB_PATH = $dbPath

    $pythonVenv = Join-Path $coreDir ".venv\Scripts\python.exe"
    if (Test-Path $pythonVenv) {
        $inserted = & $pythonVenv $tmpPyPath
    }
    else {
        $uv = Get-Command uv -ErrorAction SilentlyContinue
        Assert-True ($null -ne $uv) "uv not found (needed to run python for DB insertion)."
        $inserted = & $uv.Source run python $tmpPyPath
    }
    Assert-True ($inserted -match $jobId) "Failed to insert job (output: $inserted)"
    Remove-Item -Force $tmpPyPath
    Write-Ok "Inserted job $jobId"

    # Write logs JSONL
    Write-Info "Writing synthetic logs..."
    $jobLogPath = Join-Path $jobsLogsDir "$jobId.log"
    $nowMs = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $lines = @(
        @{ tsMs = $nowMs; level = "info"; stage = "ingest"; message = "smoke: hello" },
        @{ tsMs = $nowMs + 1; level = "info"; stage = "ingest"; message = "smoke: progress 10%" },
        @{ tsMs = $nowMs + 2; level = "warn"; stage = "ingest"; message = "smoke: warning line" }
    )
    Remove-Item -Force $jobLogPath -ErrorAction SilentlyContinue
    foreach ($l in $lines) {
        ($l | ConvertTo-Json -Compress) | Out-File -FilePath $jobLogPath -Encoding utf8 -Append
    }
    Write-Ok "Wrote logs: $jobLogPath"

    # GET job
    Write-Info "GET /jobs/{jobId}"
    $job = Invoke-CurlJson -Url "$ApiBaseUrl/api/v1/jobs/$jobId"
    Assert-True ($job.jobId -eq $jobId) "GET job mismatch"
    Assert-True ($job.status -eq "running") "Expected status=running, got $($job.status)"
    Write-Ok "Job GET OK"

    # SSE (once)
    Write-Info "GET /jobs/{jobId}/events?once=true (SSE)"
    $sseText = Invoke-CurlText -Url "$ApiBaseUrl/api/v1/jobs/$jobId/events?once=true" -CurlArgs @("-N", "-H", "Accept: text/event-stream")
    Assert-True ($sseText -match "(?m)^event:") "SSE output missing 'event:'\n$sseText"
    Assert-True ($sseText -match "(?m)^data:") "SSE output missing 'data:'\n$sseText"
    Write-Ok "SSE OK"

    # Logs
    Write-Info "GET /jobs/{jobId}/logs?limit=50"
    $logs = Invoke-CurlJson -Url "$ApiBaseUrl/api/v1/jobs/$jobId/logs?limit=50"
    Assert-True ($logs.items.Count -ge 1) "Expected logs items >= 1"
    Assert-True ([string]::IsNullOrEmpty($logs.nextCursor) -eq $false) "Expected nextCursor to be present"
    Write-Ok "Logs OK (items=$($logs.items.Count))"

    # Cancel
    Write-Info "POST /jobs/{jobId}/cancel"
    $cancel = Invoke-CurlJson -Url "$ApiBaseUrl/api/v1/jobs/$jobId/cancel" -CurlArgs @("-X", "POST")
    Assert-True ($cancel.ok -eq $true) "Cancel failed"
    Write-Ok "Cancel OK"

    # Retry
    Write-Info "POST /jobs/{jobId}/retry"
    $retryJob = Invoke-CurlJson -Url "$ApiBaseUrl/api/v1/jobs/$jobId/retry" -CurlArgs @("-X", "POST")
    Assert-True ($retryJob.status -eq "queued") "Retry expected status=queued, got $($retryJob.status)"
    Assert-True ($retryJob.jobId -ne $jobId) "Retry should create a new jobId"
    Write-Ok "Retry OK (newJobId=$($retryJob.jobId))"

    Write-Ok "PHASE 1 SMOKE PASSED"
    exit 0
}
catch {
    Write-Fail $_.Exception.Message
    if (Test-Path $backendErr) {
        Write-Host "---- backend stderr (tail) ----" -ForegroundColor DarkGray
        Get-Content $backendErr -Tail 80 | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray }
    }
    if (Test-Path $backendOut) {
        Write-Host "---- backend stdout (tail) ----" -ForegroundColor DarkGray
        Get-Content $backendOut -Tail 80 | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray }
    }
    exit 1
}
finally {
    # Restore environment variables to their prior values.
    foreach ($k in $prevEnv.Keys) {
        $val = $prevEnv[$k]
        if ($null -eq $val -or $val -eq "") {
            Remove-Item Env:$k -ErrorAction SilentlyContinue
        }
        else {
            Set-Item -Path ("Env:" + $k) -Value $val
        }
    }

    if ($backendProc -ne $null -and -not $SkipStartBackend) {
        Write-Info "Stopping backend PID $($backendProc.Id)"
        try {
            Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
        }
        catch {
            # ignore
        }
    }
}
