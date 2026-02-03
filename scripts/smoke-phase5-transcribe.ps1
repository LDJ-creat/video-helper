<#
Phase 5 Smoke Test: Real Transcribe Closed Loop (Windows PowerShell)

What this checks:
  - Start backend with worker enabled
  - Create URL job (youtube/bilibili) and/or upload job
  - Poll job state until succeeded/failed
  - (Optional) Fetch a short SSE sample to confirm progress/log events are streaming

Prereqs (for real transcribe):
  - yt-dlp available on PATH
  - ffmpeg available on PATH
  - Python deps include faster-whisper, and the model is available (or can be downloaded)

Usage examples:
  Set-ExecutionPolicy -Scope Process Bypass -Force; .\scripts\smoke-phase5-transcribe.ps1 -Url "https://www.youtube.com/watch?v=..."
  .\scripts\smoke-phase5-transcribe.ps1 -UploadFilePath "C:\\path\\to\\small.mp4"
  .\scripts\smoke-phase5-transcribe.ps1 -Url "..." -CheckSse

Notes:
  - Uses curl.exe (NOT PowerShell's curl alias)
  - Default DATA_DIR is an isolated temp folder per run
#>

[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [int]$TimeoutSec = 900,
    [switch]$SkipStartBackend,
    [string]$DataDir,
    [string]$LogCursorSecret = "dev-log-cursor-secret",

    # Convenience presets to reduce repeated args for common providers.
    # - default: keep existing behavior
    # - bilibili: cookies default, audio-only download, tiny model, SSE check, longer timeout
    [ValidateSet("default", "bilibili")]
    [string]$Profile = "default",

    [ValidateSet("faster-whisper", "placeholder")]
    [string]$TranscribeProvider = "faster-whisper",
    [string]$TranscribeModelSize = "base",
    [string]$TranscribeDevice = "cpu",
    [string]$TranscribeComputeType = "int8",

    [string]$Url,
    [string]$UploadFilePath,
    [switch]$CheckSse,

    # By default we write an evidence JSON (files + DB refs) after each job.
    # Opt-out with -NoEvidence.
    [switch]$NoEvidence,

    # Optional: help yt-dlp pass anti-bot for some providers (e.g. bilibili HTTP 412).
    [string]$YtDlpCookiesFromBrowser,
    [string]$YtDlpCookiesFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Ensure WinGet-installed tools (e.g. ffmpeg) are on PATH in fresh shells.
$winGetLinks = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"
if (Test-Path $winGetLinks) {
    $env:PATH = "$winGetLinks;$env:PATH"
}

function Write-Info([string]$Message) { Write-Host "[smoke] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "[ok] $Message" -ForegroundColor Green }
function Assert-True([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }

function Get-RepoRoot() {
    $root = Resolve-Path (Join-Path $PSScriptRoot "..")
    return $root.Path
}

function Require-Command([string]$Name, [string]$Hint) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    Assert-True ($null -ne $cmd) "$Name not found. $Hint"
    return $cmd
}

function Invoke-CurlRaw([string]$Url, [string[]]$CurlArgs = @()) {
    $curl = Require-Command -Name "curl.exe" -Hint "Install curl (Windows 10+ includes it)"
    $allArgs = @("-sS", "--max-time", "60") + $CurlArgs + @($Url)
    $out = & $curl.Source @allArgs
    if ($out -is [System.Array]) { $out = ($out -join "`n") }
    $exit = $LASTEXITCODE
    Assert-True ($exit -eq 0) "curl failed ($exit): $Url"
    return $out
}

function Get-ProcessCommandLine([int]$ProcessId) {
    try {
        $p = Get-CimInstance Win32_Process -Filter ("ProcessId=$ProcessId")
        return ($p.CommandLine + "")
    }
    catch {
        return ""
    }
}

function Ensure-PortFree([int]$Port) {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $conn) { return }

    $processId = [int]$conn.OwningProcess
    $cmd = Get-ProcessCommandLine -ProcessId $processId
    Write-Info ("Port $Port is in use by pid=$processId cmd=$cmd")

    # Best-effort: auto-kill common stale dev backends.
    # In practice on Windows the command line can vary (conda/uv/venv), so we
    # allow any Python process here to reduce false negatives during smoke runs.
    if ($cmd -match "services\\core" -or $cmd -match "python" -or $cmd -match "python.+main\\.py" -or $cmd -match "uv.+python.+main\\.py") {
        Write-Info "Stopping stale backend on port $Port (pid=$processId)..."
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 600
        $conn2 = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        Assert-True ($null -eq $conn2) "Failed to free port $Port (still in use)"
        return
    }

    throw "Port $Port is already in use by pid=$processId. Stop it or run with -SkipStartBackend. cmd=$cmd"
}

function Invoke-CurlJson([string]$Url, [string[]]$CurlArgs = @()) {
    $text = Invoke-CurlRaw -Url $Url -CurlArgs $CurlArgs
    try { return $text | ConvertFrom-Json }
    catch { throw "Expected JSON but got: $text" }
}

function Invoke-CurlJsonWithStatus([string]$Url, [string[]]$CurlArgs = @()) {
    $text = Invoke-CurlRaw -Url $Url -CurlArgs ($CurlArgs + @("-w", "`n%{http_code}"))
    $lines = $text -split "`n"
    Assert-True ($lines.Length -ge 2) "Unexpected curl output for status"
    $statusLine = $lines[$lines.Length - 1].Trim()
    $body = ($lines[0..($lines.Length - 2)] -join "`n")
    $status = 0
    [void][int]::TryParse($statusLine, [ref]$status)

    $json = $null
    if ($body.Trim() -ne "") {
        try { $json = $body | ConvertFrom-Json } catch { $json = $null }
    }

    return [pscustomobject]@{ Status = $status; BodyText = $body; Json = $json }
}

function Wait-ForHealth([string]$HealthUrl, [int]$TimeoutSeconds) {
    # Fail fast if curl.exe is not available; otherwise we'd loop silently.
    [void](Require-Command -Name "curl.exe" -Hint "Install curl (Windows 10+ includes it)")
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = $null
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-CurlJson -Url $HealthUrl
            if ($resp.status -and $resp.ready -ne $null) { return $resp }
        }
        catch {
            $lastError = $_
            Start-Sleep -Milliseconds 500
            continue
        }
        Start-Sleep -Milliseconds 500
    }
    if ($null -ne $lastError) {
        throw "Timed out waiting for health: $HealthUrl. Last error: $lastError"
    }
    throw "Timed out waiting for health: $HealthUrl"
}

function Wait-ForJobDone([string]$JobId, [int]$TimeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $last = $null
    while ((Get-Date) -lt $deadline) {
        $job = Invoke-CurlJson -Url ("$ApiBaseUrl/api/v1/jobs/$JobId")
        $status = $job.status
        $stage = $job.stage
        $progress = $job.progress
        $line = "status=$status stage=$stage progress=$progress"
        if ($line -ne $last) { Write-Info $line; $last = $line }
        if ($status -in @("succeeded", "failed", "canceled")) { return $job }
        Start-Sleep -Seconds 1
    }
    throw "Timed out waiting for job: $JobId"
}

function Maybe-CheckSse([string]$JobId) {
    if (-not $CheckSse) { return }
    Write-Info "Checking SSE output (5s)..."
    $curl = Require-Command -Name "curl.exe" -Hint "Install curl (Windows 10+ includes it)"
    $allArgs = @("-sS", "-N", "--max-time", "5", ("$ApiBaseUrl/api/v1/jobs/$JobId/events?once=false"))
    $text = & $curl.Source @allArgs
    if ($text -is [System.Array]) { $text = ($text -join "`n") }
    $exit = $LASTEXITCODE
    # curl returns 28 on timeout; for SSE probing that's expected.
    Assert-True (($exit -eq 0) -or ($exit -eq 28)) "curl failed ($exit): $ApiBaseUrl/api/v1/jobs/$JobId/events?once=false"
    Assert-True ($text -match "event:") "Expected SSE frames but got: $text"
    Write-Ok "SSE frames received"
}

function Write-SmokeEvidence([string]$JobId) {
    if ($NoEvidence) { return }

    $outDir = Join-Path $repoRoot "_bmad-output\implementation-artifacts"
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $outPath = Join-Path $outDir ("smoke-evidence-{0}.json" -f $JobId)

    $py = Join-Path $coreDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    }
    if ([string]::IsNullOrEmpty($py)) {
        Write-Info "Skip evidence: python not found"
        return
    }

    $script = Join-Path $coreDir "scripts\report_smoke_evidence.py"
    if (-not (Test-Path $script)) {
        Write-Info "Skip evidence: report_smoke_evidence.py not found"
        return
    }

    try {
        & $py $script --data-dir $DataDir --job-id $JobId --out $outPath | Out-Null
        Write-Ok ("Evidence written: {0}" -f $outPath)
    }
    catch {
        Write-Info ("Evidence collection failed: {0}" -f $_)
    }
}

$repoRoot = Get-RepoRoot
$coreDir = Join-Path $repoRoot "services\core"

# Apply profile defaults (only when user didn't explicitly set those params/envs).
if ($Profile -eq "bilibili") {
    if (-not $PSBoundParameters.ContainsKey("TimeoutSec")) {
        $TimeoutSec = 1200
    }
    if (-not $PSBoundParameters.ContainsKey("TranscribeModelSize")) {
        $TranscribeModelSize = "tiny"
    }
    if (-not $PSBoundParameters.ContainsKey("CheckSse")) {
        $CheckSse = $true
    }

    if (-not $PSBoundParameters.ContainsKey("DataDir") -or [string]::IsNullOrEmpty($DataDir)) {
        if (Test-Path "D:\\") {
            $DataDir = "D:\\vh-smoke-data"
        }
        else {
            $DataDir = Join-Path $env:TEMP "vh-smoke-data"
        }
    }

    # Prefer an explicit -YtDlpCookiesFile/-YtDlpCookiesFromBrowser, but fall back to repo cookie export if present.
    if ([string]::IsNullOrEmpty($YtDlpCookiesFromBrowser) -and [string]::IsNullOrEmpty($YtDlpCookiesFile)) {
        $defaultCookie = Join-Path $repoRoot "www.bilibili.com_cookies.txt"
        if (Test-Path $defaultCookie) {
            $YtDlpCookiesFile = $defaultCookie
        }
    }

    # Reduce format/merge complexity and speed up the pipeline.
    if ([string]::IsNullOrEmpty($env:YTDLP_FORMAT)) {
        $env:YTDLP_FORMAT = "bestaudio/best"
    }
}

if ([string]::IsNullOrEmpty($DataDir)) {
    $DataDir = Join-Path $env:TEMP ("video-helper-smoke-phase5\\{0}" -f ([guid]::NewGuid().ToString("N")))
}
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
$DataDir = (Resolve-Path $DataDir).Path

$backendProc = $null
if (-not $SkipStartBackend) {
    Ensure-PortFree -Port 8000
    Write-Info "Starting backend (worker enabled)..."

    $env:DATA_DIR = $DataDir
    $env:LOG_CURSOR_SECRET = $LogCursorSecret
    $env:WORKER_ENABLE = "1"
    $env:MAX_CONCURRENT_JOBS = "1"

    $env:TRANSCRIBE_PROVIDER = $TranscribeProvider
    $env:TRANSCRIBE_MODEL_SIZE = $TranscribeModelSize
    $env:TRANSCRIBE_DEVICE = $TranscribeDevice
    $env:TRANSCRIBE_COMPUTE_TYPE = $TranscribeComputeType

    if (-not [string]::IsNullOrEmpty($YtDlpCookiesFromBrowser)) {
        $env:YTDLP_COOKIES_FROM_BROWSER = $YtDlpCookiesFromBrowser
    }
    if (-not [string]::IsNullOrEmpty($YtDlpCookiesFile)) {
        $env:YTDLP_COOKIES_FILE = $YtDlpCookiesFile
    }

    $py = Join-Path $coreDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        $py = (Require-Command -Name "python" -Hint "Install Python or add it to PATH").Source
    }
    $backendProc = Start-Process -FilePath $py -ArgumentList @("main.py") -WorkingDirectory $coreDir -PassThru -NoNewWindow
}

try {
    $health = Wait-ForHealth -HealthUrl "$ApiBaseUrl/api/v1/health" -TimeoutSeconds 60
    Write-Ok "Health ready: $($health.status)"

    if (-not [string]::IsNullOrEmpty($Url)) {
        Write-Info "Creating URL job..."
        $sourceType = "youtube"
        if ($Url -match "bilibili\.com" -or $Url -match "b23\.tv") { $sourceType = "bilibili" }

        if ($sourceType -eq "bilibili" -and [string]::IsNullOrEmpty($YtDlpCookiesFromBrowser) -and [string]::IsNullOrEmpty($YtDlpCookiesFile)) {
            Write-Info "Tip: bilibili may return HTTP 412 without cookies. Consider -YtDlpCookiesFromBrowser edge (or chrome)."
        }
        $payload = @{ title = "smoke-url"; sourceType = $sourceType; sourceUrl = $Url } | ConvertTo-Json -Compress
        $tmp = Join-Path $env:TEMP ("smoke_job_{0}.json" -f ([guid]::NewGuid().ToString("N")))
        [System.IO.File]::WriteAllText($tmp, $payload, (New-Object System.Text.UTF8Encoding($false)))

        $resp = Invoke-CurlJsonWithStatus -Url "$ApiBaseUrl/api/v1/jobs" -CurlArgs @("-H", "Content-Type: application/json", "--data-binary", "@$tmp")
        Assert-True ($resp.Status -eq 200) "Create URL job failed (HTTP $($resp.Status)): $($resp.BodyText)"
        $created = $resp.Json
        Assert-True ($null -ne $created.jobId) "Create URL job returned unexpected JSON: $($resp.BodyText)"
        Write-Ok "URL job created: $($created.jobId)"
        Maybe-CheckSse -JobId $created.jobId
        $final = Wait-ForJobDone -JobId $created.jobId -TimeoutSeconds $TimeoutSec
        Write-SmokeEvidence -JobId $created.jobId
        if ($final.status -ne "succeeded") {
            $err = $final.error
            $errCode = $null
            $errMsg = $null
            $errDetails = $null
            if ($null -ne $err) {
                $errCode = $err.code
                $errMsg = $err.message
                $errDetails = $err.details
            }
            throw ("URL job failed: jobId={0} stage={1} progress={2} errorCode={3} message={4} details={5}" -f $final.jobId, $final.stage, $final.progress, $errCode, $errMsg, ($errDetails | ConvertTo-Json -Compress -Depth 6))
        }
        Write-Ok "URL job succeeded"
    }

    if (-not [string]::IsNullOrEmpty($UploadFilePath)) {
        Assert-True (Test-Path $UploadFilePath) "UploadFilePath not found: $UploadFilePath"
        Write-Info "Creating upload job..."
        $resp = Invoke-CurlJsonWithStatus -Url "$ApiBaseUrl/api/v1/jobs" -CurlArgs @(
            "-F", "sourceType=upload",
            "-F", ("file=@{0}" -f $UploadFilePath)
        )
        Assert-True ($resp.Status -eq 200) "Create upload job failed (HTTP $($resp.Status)): $($resp.BodyText)"
        $created = $resp.Json
        Assert-True ($null -ne $created.jobId) "Create upload job returned unexpected JSON: $($resp.BodyText)"
        Write-Ok "Upload job created: $($created.jobId)"
        Maybe-CheckSse -JobId $created.jobId
        $final = Wait-ForJobDone -JobId $created.jobId -TimeoutSeconds $TimeoutSec
        Write-SmokeEvidence -JobId $created.jobId
        if ($final.status -ne "succeeded") {
            $err = $final.error
            $errCode = $null
            $errMsg = $null
            $errDetails = $null
            if ($null -ne $err) {
                $errCode = $err.code
                $errMsg = $err.message
                $errDetails = $err.details
            }
            throw ("Upload job failed: jobId={0} stage={1} progress={2} errorCode={3} message={4} details={5}" -f $final.jobId, $final.stage, $final.progress, $errCode, $errMsg, ($errDetails | ConvertTo-Json -Compress -Depth 6))
        }
        Write-Ok "Upload job succeeded"
    }

    if ([string]::IsNullOrEmpty($Url) -and [string]::IsNullOrEmpty($UploadFilePath)) {
        Write-Info "No -Url or -UploadFilePath provided; nothing to do."
    }
}
finally {
    if ($backendProc -ne $null -and -not $backendProc.HasExited) {
        Write-Info "Stopping backend (pid=$($backendProc.Id))"
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
}
