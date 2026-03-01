<#
Phase 6 Smoke Test: Closed Loop (bilibili URL -> download -> audio -> transcribe -> LLM analyze -> assemble_result -> assets/result readable)

What this checks:
  - Start backend with worker enabled
  - Create bilibili URL job (default BV1jgifB7EAp)
  - Poll job state until succeeded/failed
  - Validate latest result payload is renderable
  - Validate an asset contentUrl is readable (Range 1KB)

Notes:
  - Uses curl.exe (NOT PowerShell's curl alias)
  - Avoids printing sensitive env values (e.g. LLM_API_KEY)
  - Relies on services/core/.env for LLM settings; script only sets runtime isolation vars
#>

[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [int]$TimeoutSec = 1200,
    [switch]$SkipStartBackend,
    [string]$DataDir,
    [string]$LogCursorSecret = "dev-log-cursor-secret",

    [ValidateSet("default", "bilibili")]
    [string]$Profile = "bilibili",

    [ValidateSet("faster-whisper", "placeholder")]
    [string]$TranscribeProvider = "faster-whisper",
    [string]$TranscribeModelSize = "tiny",
    [string]$TranscribeDevice = "cpu",
    [string]$TranscribeComputeType = "int8",

    [string]$Url = "https://www.bilibili.com/video/BV1jgifB7EAp/?spm_id_from=333.337.search-card.all.click&vd_source=8e03b1a6cd89d2b50af0c43b7de269ff",

    [switch]$NoEvidence,

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

function Invoke-CurlJson([string]$Url, [string[]]$CurlArgs = @()) {
    $text = Invoke-CurlRaw -Url $Url -CurlArgs $CurlArgs
    try { return $text | ConvertFrom-Json }
    catch { throw "Expected JSON but got: $text" }
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

    if ($cmd -match "services\\core" -or $cmd -match "python" -or $cmd -match "main\\.py") {
        Write-Info "Stopping stale backend on port $Port (pid=$processId)..."
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 600
        $conn2 = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        Assert-True ($null -eq $conn2) "Failed to free port $Port (still in use)"
        return
    }

    throw "Port $Port is already in use by pid=$processId. Stop it or run with -SkipStartBackend. cmd=$cmd"
}

function Wait-ForHealth([string]$HealthUrl, [int]$TimeoutSeconds) {
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

function Write-SmokeEvidence([string]$JobId) {
    if ($NoEvidence) { return }

    $outDir = Join-Path $repoRoot "_bmad-output\implementation-artifacts"
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $outPath = Join-Path $outDir ("smoke-evidence-closed-loop-{0}.json" -f $JobId)

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
        & $py $script --data-dir $DataDir --job-id $JobId --max-files 20 --out $outPath | Out-Null
        Write-Ok ("Evidence written: {0}" -f $outPath)
    }
    catch {
        Write-Info ("Evidence collection failed: {0}" -f $_)
    }
}

$repoRoot = Get-RepoRoot
$coreDir = Join-Path $repoRoot "services\core"

# Profile defaults
if ($Profile -eq "bilibili") {
    if (-not $PSBoundParameters.ContainsKey("TimeoutSec")) {
        $TimeoutSec = 1200
    }

    if (-not $PSBoundParameters.ContainsKey("DataDir") -or [string]::IsNullOrEmpty($DataDir)) {
        if (Test-Path "D:\") {
            $DataDir = "D:\vh-smoke-data"
        }
        else {
            $DataDir = Join-Path $env:TEMP "vh-smoke-data"
        }
    }

    if ([string]::IsNullOrEmpty($YtDlpCookiesFromBrowser) -and [string]::IsNullOrEmpty($YtDlpCookiesFile)) {
        $defaultCookie = Join-Path $repoRoot "www.bilibili.com_cookies.txt"
        if (Test-Path $defaultCookie) {
            $YtDlpCookiesFile = $defaultCookie
        }
    }

    # Closed-loop requires keyframes assets; ensure we download video+audio.
    if ([string]::IsNullOrEmpty($env:YTDLP_FORMAT)) {
        $env:YTDLP_FORMAT = "bestvideo+bestaudio/best"
    }
}

if ([string]::IsNullOrEmpty($DataDir)) {
    $DataDir = Join-Path $env:TEMP ("video-helper-smoke-closed-loop\{0}" -f ([guid]::NewGuid().ToString("N")))
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

    # LLM calls can have slow first-byte latency; keep smoke stable.
    if ([string]::IsNullOrEmpty($env:LLM_TIMEOUT_S)) {
        $env:LLM_TIMEOUT_S = "180"
    }
    if ([string]::IsNullOrEmpty($env:LLM_PREFLIGHT_TIMEOUT_S)) {
        $env:LLM_PREFLIGHT_TIMEOUT_S = "60"
    }
    if ([string]::IsNullOrEmpty($env:LLM_MAX_ATTEMPTS)) {
        $env:LLM_MAX_ATTEMPTS = "3"
    }
    if ([string]::IsNullOrEmpty($env:LLM_PLAN_MAX_SEGMENTS)) {
        $env:LLM_PLAN_MAX_SEGMENTS = "40"
    }
    if ([string]::IsNullOrEmpty($env:LLM_PLAN_MAX_CHARS)) {
        $env:LLM_PLAN_MAX_CHARS = "8000"
    }

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

    $smokePy = Join-Path $coreDir "scripts\smoke_closed_loop.py"
    Assert-True (Test-Path $smokePy) "smoke python not found: $smokePy"

    $py = Join-Path $coreDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        $py = (Require-Command -Name "python" -Hint "Install Python or add it to PATH").Source
    }

    $summaryPath = Join-Path $DataDir ("smoke_closed_loop_summary_{0}.json" -f ([guid]::NewGuid().ToString("N")))

    Write-Info "Running closed-loop validation (python)..."
    & $py $smokePy --api-base $ApiBaseUrl --timeout-sec $TimeoutSec --source-type "bilibili" --url $Url --summary-out $summaryPath
    $exit = $LASTEXITCODE
    Assert-True ($exit -eq 0) "closed-loop smoke python failed (exit=$exit). See logs above."

    if (Test-Path $summaryPath) {
        try {
            $summary = Get-Content -Raw -Path $summaryPath | ConvertFrom-Json
            if ($summary.ok -and $summary.jobId) {
                Write-SmokeEvidence -JobId ($summary.jobId + "")
            }
        }
        catch {
            Write-Info "Summary parse failed; skip evidence"
        }
    }

    Write-Ok "Closed-loop smoke succeeded"
}
finally {
    if ($backendProc -ne $null -and -not $backendProc.HasExited) {
        Write-Info "Stopping backend (pid=$($backendProc.Id))"
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
}
