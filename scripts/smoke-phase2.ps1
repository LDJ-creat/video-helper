<#
Phase 2 Smoke Test (Windows PowerShell)

One-click flow:
  0) (Optional) Run backend unit tests (unittest)
  1) Start backend (services/core)
  2) Wait for /api/v1/health
  3) Start web (apps/web) with NEXT_PUBLIC_API_BASE_URL pointing to backend
  4) Wait for /ingest page to be reachable
  5) Backend API smoke:
     - POST /api/v1/jobs (JSON)  -> expect queued + ids
     - POST /api/v1/jobs (JSON invalid url) -> expect 400 + error envelope
     - POST /api/v1/jobs (multipart upload) ->
         * if ffprobe exists: expect 200
         * else: expect 400 with error code FFMPEG_MISSING (dependency missing)
  6) Basic web smoke:
     - GET / and /ingest return 200 and contain expected strings

Usage:
  .\scripts\smoke-phase2.ps1
  .\scripts\smoke-phase2.ps1 -WebMode dev
  .\scripts\smoke-phase2.ps1 -UploadFilePath "C:\\path\\to\\small.mp4"
  .\scripts\smoke-phase2.ps1 -SkipStartBackend -SkipStartWeb
  Set-ExecutionPolicy -Scope Process Bypass -Force; .\scripts\smoke-phase2.ps1

Notes:
  - Uses curl.exe (NOT PowerShell's curl alias).
  - Default DATA_DIR is repo-root\data.
  - Upload test requires a local file path (UploadFilePath). If not provided, upload test is skipped.
#>

[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$WebBaseUrl = "http://127.0.0.1:3000",
    [ValidateSet("prod", "dev")]
    [string]$WebMode = "prod",
    [int]$WebPort = 3000,
    [int]$TimeoutSec = 60,
    [switch]$SkipStartBackend,
    [switch]$SkipStartWeb,
    [switch]$SkipBackendUnitTests,
    [string]$DataDir,
    [string]$LogCursorSecret = "dev-log-cursor-secret",
    [string]$UploadFilePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) { Write-Host "[smoke] $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "[ok] $Message" -ForegroundColor Green }
function Write-Fail([string]$Message) { Write-Host "[fail] $Message" -ForegroundColor Red }
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
    $allArgs = @("-sS", "--max-time", "20") + $CurlArgs + @($Url)
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

function Invoke-CurlJsonWithStatus([string]$Url, [string[]]$CurlArgs = @()) {
    # Use curl's status formatter. The last line is HTTP code.
    $text = Invoke-CurlRaw -Url $Url -CurlArgs ($CurlArgs + @("-w", "`n%{http_code}"))
    $lines = $text -split "`n"
    Assert-True ($lines.Length -ge 2) "Unexpected curl output for status"
    $statusLine = $lines[$lines.Length - 1].Trim()
    $body = ($lines[0..($lines.Length - 2)] -join "`n")
    $status = 0
    [void][int]::TryParse($statusLine, [ref]$status)
    Assert-True ($status -ge 100) "Failed to parse HTTP status from: $statusLine"

    $json = $null
    if ($body.Trim() -ne "") {
        try { $json = $body | ConvertFrom-Json } catch { $json = $null }
    }

    return [pscustomobject]@{ Status = $status; BodyText = $body; Json = $json }
}

function Wait-ForHealth([string]$HealthUrl, [int]$TimeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-CurlJson -Url $HealthUrl
            if ($resp.status -and $resp.ready -ne $null) { return $resp }
        }
        catch {
            Start-Sleep -Milliseconds 400
            continue
        }
        Start-Sleep -Milliseconds 400
    }
    throw "Timed out waiting for health: $HealthUrl"
}

function Wait-ForHttp200([string]$Url, [int]$TimeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $result = Invoke-CurlJsonWithStatus -Url $Url -CurlArgs @("-H", "Accept: text/html")
            if ($result.Status -eq 200) { return $result.BodyText }
        }
        catch {
            Start-Sleep -Milliseconds 400
            continue
        }
        Start-Sleep -Milliseconds 400
    }
    throw "Timed out waiting for 200: $Url"
}

function Write-TempUtf8NoBom([string]$Content) {
    $path = Join-Path $env:TEMP ("smoke_json_{0}.json" -f ([guid]::NewGuid().ToString("N")))
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($path, $Content, $enc)
    return $path
}

function Test-TcpPortFree([int]$Port) {
    # Probe whether something is already listening.
    foreach ($targetHost in @("127.0.0.1", "::1")) {
        try {
            $client = New-Object System.Net.Sockets.TcpClient
            $iar = $client.BeginConnect($targetHost, $Port, $null, $null)
            $ok = $iar.AsyncWaitHandle.WaitOne(150)
            if ($ok -and $client.Connected) {
                $client.Close()
                return $false
            }
            $client.Close()
        }
        catch {
            # ignore; treat as not listening on this host
        }
    }
    return $true
}


function Get-PythonRunner([string]$CoreDir) {
    $pythonVenv = Join-Path $CoreDir ".venv\Scripts\python.exe"
    if (Test-Path $pythonVenv) {
        return [pscustomobject]@{ Kind = "venv"; Path = $pythonVenv; ArgsPrefix = @() }
    }

    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -ne $uv) {
        return [pscustomobject]@{ Kind = "uv"; Path = $uv.Source; ArgsPrefix = @("run", "python") }
    }

    throw "Neither services/core/.venv nor uv found. Install uv or create a venv under services/core/.venv."
}

function Run-Backend-Unittest([string]$RepoRoot, [string]$CoreDir, $Python) {
    $testsDir = Join-Path $CoreDir "tests"
    if (-not (Test-Path $testsDir)) {
        Write-Info "No backend tests dir found: $testsDir (skip)"
        return
    }

    # Ensure imports work when running tests directly (tests import `core.*`).
    $coreSrc = Join-Path $CoreDir "src"
    $existingPyPath = $env:PYTHONPATH
    if ([string]::IsNullOrEmpty($existingPyPath)) {
        $env:PYTHONPATH = $coreSrc
    }
    else {
        $env:PYTHONPATH = ($coreSrc + ";" + $existingPyPath)
    }

    Write-Info "Running backend unit tests (unittest discover)..."
    $args = @() + $Python.ArgsPrefix + @("-m", "unittest", "discover", "-s", "tests", "-p", "test*.py")
    $p = Start-Process -FilePath $Python.Path -ArgumentList $args -WorkingDirectory $CoreDir -NoNewWindow -Wait -PassThru
    Assert-True ($p.ExitCode -eq 0) "Backend unit tests failed (exit=$($p.ExitCode))"
    Write-Ok "Backend unit tests OK"
}

function Ensure-PnpmDeps([string]$WebDir) {
    # On Windows, pnpm is often a PowerShell script (pnpm.ps1) which cannot be started via Start-Process.
    # Use corepack.cmd (an executable) to run pnpm reliably.
    $corepack = Get-Command corepack.cmd -ErrorAction SilentlyContinue
    if ($null -eq $corepack) {
        $corepack = Get-Command corepack -ErrorAction SilentlyContinue
    }
    Assert-True ($null -ne $corepack) "corepack not found. Install Node.js 20+ (with corepack)."

    $pnpmRunner = [pscustomobject]@{ Path = $corepack.Source; ArgsPrefix = @("pnpm") }

    # Always run install (idempotent) to keep node_modules aligned with package.json after merges.
    Write-Info "Installing web dependencies (pnpm install)..."
    $p = Start-Process -FilePath $pnpmRunner.Path -ArgumentList ($pnpmRunner.ArgsPrefix + @("install")) -WorkingDirectory $WebDir -NoNewWindow -Wait -PassThru
    Assert-True ($p.ExitCode -eq 0) "pnpm install failed (exit=$($p.ExitCode))"
    Write-Ok "pnpm install OK"

    return $pnpmRunner
}

$repoRoot = Get-RepoRoot
$coreDir = Join-Path $repoRoot "services\core"
$webDir = Join-Path $repoRoot "apps\web"

# Default to an isolated temp data dir so existing core.sqlite3 schema doesn't break smoke runs.
if (-not $PSBoundParameters.ContainsKey("DataDir") -or [string]::IsNullOrEmpty($DataDir)) {
    $DataDir = Join-Path $env:TEMP ("video-helper-smoke-phase2\\{0}" -f ([guid]::NewGuid().ToString("N")))
}
$dataDirResolved = (Resolve-Path -Path $DataDir -ErrorAction SilentlyContinue)
if ($null -eq $dataDirResolved) {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
    $dataDirResolved = Resolve-Path $DataDir
}
$DataDir = $dataDirResolved.Path

$prevEnv = @{}
foreach ($k in @(
        "DATA_DIR",
        "LOG_CURSOR_SECRET",
        "NEXT_PUBLIC_API_BASE_URL",
        "PYTHONPATH"
    )) {
    $item = Get-Item -Path ("Env:" + $k) -ErrorAction SilentlyContinue
    $prevEnv[$k] = if ($null -ne $item) { $item.Value } else { $null }
}

$backendProc = $null
$webProc = $null
$backendOut = Join-Path $DataDir "smoke-phase2-backend.stdout.log"
$backendErr = Join-Path $DataDir "smoke-phase2-backend.stderr.log"
$webOut = Join-Path $DataDir "smoke-phase2-web.stdout.log"
$webErr = Join-Path $DataDir "smoke-phase2-web.stderr.log"

$tmpFiles = @()

try {
    Write-Info "Repo root: $repoRoot"
    Write-Info "DATA_DIR: $DataDir"
    Write-Info "ApiBaseUrl: $ApiBaseUrl"
    # If caller didn't specify WebBaseUrl, pick a free port to avoid collisions.
    $webBaseUrlProvided = $PSBoundParameters.ContainsKey("WebBaseUrl")
    $webPortProvided = $PSBoundParameters.ContainsKey("WebPort")
    if (-not $webBaseUrlProvided) {
        if (-not $webPortProvided) {
            foreach ($p in 3000..3010) {
                if (Test-TcpPortFree -Port $p) { $WebPort = $p; break }
            }
        }
        $WebBaseUrl = "http://127.0.0.1:$WebPort"
    }
    Write-Info "WebBaseUrl: $WebBaseUrl (mode=$WebMode)"

    $python = Get-PythonRunner -CoreDir $coreDir

    if (-not $SkipBackendUnitTests) {
        Run-Backend-Unittest -RepoRoot $repoRoot -CoreDir $coreDir -Python $python
    }
    else {
        Write-Info "SkipBackendUnitTests enabled."
    }

    if (-not $SkipStartBackend) {
        Write-Info "Starting backend (services/core)..."
        $env:DATA_DIR = $DataDir
        $env:LOG_CURSOR_SECRET = $LogCursorSecret

        if ($python.Kind -eq "venv") {
            $backendProc = Start-Process -FilePath $python.Path -ArgumentList @("main.py") -WorkingDirectory $coreDir -NoNewWindow -PassThru -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr
        }
        else {
            $backendProc = Start-Process -FilePath $python.Path -ArgumentList @("run", "python", "main.py") -WorkingDirectory $coreDir -NoNewWindow -PassThru -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr
        }
        Write-Info "Backend PID: $($backendProc.Id)"
    }
    else {
        Write-Info "SkipStartBackend enabled; assuming backend already running."
    }

    $healthUrl = "$ApiBaseUrl/api/v1/health"
    Write-Info "Waiting for health: $healthUrl"
    $health = Wait-ForHealth -HealthUrl $healthUrl -TimeoutSeconds $TimeoutSec
    Write-Ok "Backend health OK (ready=$($health.ready))"

    if (-not $SkipStartWeb) {
        $pnpm = Ensure-PnpmDeps -WebDir $webDir

        $env:NEXT_PUBLIC_API_BASE_URL = $ApiBaseUrl
        $env:PORT = "$WebPort"

        if ($WebMode -eq "prod") {
            Write-Info "Building web (pnpm build)..."
            $pBuild = Start-Process -FilePath $pnpm.Path -ArgumentList ($pnpm.ArgsPrefix + @("build")) -WorkingDirectory $webDir -NoNewWindow -Wait -PassThru
            Assert-True ($pBuild.ExitCode -eq 0) "pnpm build failed (exit=$($pBuild.ExitCode))"
            Write-Ok "Web build OK"

            Write-Info "Starting web (pnpm start)..."
            $webProc = Start-Process -FilePath $pnpm.Path -ArgumentList ($pnpm.ArgsPrefix + @("start")) -WorkingDirectory $webDir -NoNewWindow -PassThru -RedirectStandardOutput $webOut -RedirectStandardError $webErr
        }
        else {
            Write-Info "Starting web (pnpm dev)..."
            $webProc = Start-Process -FilePath $pnpm.Path -ArgumentList ($pnpm.ArgsPrefix + @("dev")) -WorkingDirectory $webDir -NoNewWindow -PassThru -RedirectStandardOutput $webOut -RedirectStandardError $webErr
        }

        Write-Info "Web PID: $($webProc.Id)"

        Start-Sleep -Seconds 1
        if ($webProc.HasExited) {
            throw "Web process exited early (exit=$($webProc.ExitCode)). See $webErr"
        }
    }
    else {
        Write-Info "SkipStartWeb enabled; assuming web already running."
    }

    $ingestUrl = "$WebBaseUrl/ingest"
    Write-Info "Waiting for web page: $ingestUrl"
    $ingestHtml = Wait-ForHttp200 -Url $ingestUrl -TimeoutSeconds $TimeoutSec
    Assert-True ($ingestHtml -match "创建视频分析") "Web /ingest did not contain expected heading"
    Assert-True ($ingestHtml -match "粘贴链接") "Web /ingest did not contain expected tab label"
    Assert-True ($ingestHtml -match "上传文件") "Web /ingest did not contain expected tab label"
    Write-Ok "Web /ingest OK"

    $homeUrl = "$WebBaseUrl/"
    Write-Info "GET web home: $homeUrl"
    $homeHtml = Wait-ForHttp200 -Url $homeUrl -TimeoutSeconds 10
    Assert-True ($homeHtml.Length -gt 100) "Web / returned unexpectedly small HTML"
    Write-Ok "Web / OK"

    # Backend API: create job (JSON)
    Write-Info "POST /api/v1/jobs (JSON url)"
    $createJson = '{"sourceType":"youtube","sourceUrl":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","title":"smoke-phase2"}'
    $createJsonPath = Write-TempUtf8NoBom -Content $createJson
    $tmpFiles += $createJsonPath
    $createdResp = Invoke-CurlJsonWithStatus -Url "$ApiBaseUrl/api/v1/jobs" -CurlArgs @(
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "--data-binary", ("@" + $createJsonPath)
    )
    Assert-True ($createdResp.Status -eq 200) "Expected 200 for create job (JSON), got $($createdResp.Status). Body=$($createdResp.BodyText)"
    $created = $createdResp.Json
    Assert-True ($created.jobId -and $created.projectId) "Expected jobId/projectId in response"
    Assert-True ($created.status -eq "queued") "Expected status=queued, got $($created.status)"
    Assert-True ($created.createdAtMs -gt 0) "Expected createdAtMs"
    Write-Ok "Backend create job (JSON) OK (jobId=$($created.jobId))"

    # Backend API: invalid url -> 400
    Write-Info "POST /api/v1/jobs (JSON invalid url)"
    $badJson = '{"sourceType":"youtube","sourceUrl":"file:///c:/x.mp4"}'
    $badJsonPath = Write-TempUtf8NoBom -Content $badJson
    $tmpFiles += $badJsonPath
    $badResp = Invoke-CurlJsonWithStatus -Url "$ApiBaseUrl/api/v1/jobs" -CurlArgs @(
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "--data-binary", ("@" + $badJsonPath)
    )
    Assert-True ($badResp.Status -eq 400) "Expected 400 for invalid sourceUrl, got $($badResp.Status)"
    Assert-True ($null -ne $badResp.Json) "Expected JSON error envelope"
    $badCode = $null
    if ($badResp.Json.PSObject.Properties.Name -contains "code") { $badCode = $badResp.Json.code }
    if (-not $badCode -and ($badResp.Json.PSObject.Properties.Name -contains "error")) { $badCode = $badResp.Json.error.code }
    Assert-True (-not [string]::IsNullOrEmpty($badCode)) "Expected error envelope code"
    Write-Ok "Backend invalid url validation OK (code=$badCode)"

    # Backend API: upload (optional)
    if ($UploadFilePath -and $UploadFilePath.Trim() -ne "") {
        $uploadResolved = Resolve-Path -Path $UploadFilePath -ErrorAction Stop
        $uploadPath = $uploadResolved.Path

        $extRaw = [System.IO.Path]::GetExtension($uploadPath)
        if ($null -eq $extRaw) { $extRaw = "" }
        $ext = $extRaw.ToLowerInvariant()
        Assert-True ($ext -in @(".mp4", ".mkv", ".webm", ".mov")) "UploadFilePath must be .mp4/.mkv/.webm/.mov"

        $ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
        $expectSuccess = ($null -ne $ffprobe)
        Write-Info "POST /api/v1/jobs (multipart upload) file=$uploadPath (ffprobePresent=$expectSuccess)"

        $uploadResp = Invoke-CurlJsonWithStatus -Url "$ApiBaseUrl/api/v1/jobs" -CurlArgs @(
            "-X", "POST",
            "-F", "sourceType=upload",
            "-F", "title=smoke-upload",
            "-F", ("file=@" + $uploadPath)
        )

        if ($expectSuccess) {
            Assert-True ($uploadResp.Status -eq 200) "Expected 200 for upload when ffprobe exists, got $($uploadResp.Status). Body=$($uploadResp.BodyText)"
            Assert-True ($uploadResp.Json.jobId -and $uploadResp.Json.projectId) "Expected jobId/projectId in upload response"
            Write-Ok "Backend create job (upload) OK (jobId=$($uploadResp.Json.jobId))"

            # Best-effort: verify file landed under DATA_DIR/{projectId}/uploads/{jobId}
            $projDir = Join-Path $DataDir $uploadResp.Json.projectId
            $uploadsDir = Join-Path $projDir ("uploads\\" + $uploadResp.Json.jobId)
            Assert-True (Test-Path $uploadsDir) "Expected upload dir exists: $uploadsDir"
            $files = Get-ChildItem -Path $uploadsDir -File -ErrorAction SilentlyContinue
            Assert-True ($files.Count -ge 1) "Expected at least one file in upload dir: $uploadsDir"
            Write-Ok "Upload file landed OK ($($files[0].FullName))"
        }
        else {
            Assert-True ($uploadResp.Status -eq 400) "Expected 400 for upload when ffprobe missing, got $($uploadResp.Status). Body=$($uploadResp.BodyText)"
            $uploadCode = $null
            if ($uploadResp.Json.PSObject.Properties.Name -contains "code") { $uploadCode = $uploadResp.Json.code }
            if (-not $uploadCode -and ($uploadResp.Json.PSObject.Properties.Name -contains "error")) { $uploadCode = $uploadResp.Json.error.code }
            Assert-True ($uploadCode -eq "FFMPEG_MISSING") "Expected code=FFMPEG_MISSING, got $uploadCode"
            Write-Ok "Backend upload correctly reports missing ffprobe (FFMPEG_MISSING)"
        }
    }
    else {
        Write-Info "UploadFilePath not provided; skipping upload smoke."
    }

    Write-Ok "PHASE 2 SMOKE PASSED"
    exit 0
}
catch {
    Write-Fail $_.Exception.Message

    if (Test-Path $backendErr) {
        Write-Host "---- backend stderr (tail) ----" -ForegroundColor DarkGray
        Get-Content $backendErr -Tail 120 | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray }
    }
    if (Test-Path $backendOut) {
        Write-Host "---- backend stdout (tail) ----" -ForegroundColor DarkGray
        Get-Content $backendOut -Tail 60 | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray }
    }
    if (Test-Path $webErr) {
        Write-Host "---- web stderr (tail) ----" -ForegroundColor DarkGray
        Get-Content $webErr -Tail 120 | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray }
    }
    if (Test-Path $webOut) {
        Write-Host "---- web stdout (tail) ----" -ForegroundColor DarkGray
        Get-Content $webOut -Tail 60 | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray }
    }

    exit 1
}
finally {
    foreach ($p in $tmpFiles) {
        try { Remove-Item -Force -Path $p -ErrorAction SilentlyContinue } catch { }
    }

    foreach ($k in $prevEnv.Keys) {
        $val = $prevEnv[$k]
        if ($null -eq $val -or $val -eq "") {
            Remove-Item Env:$k -ErrorAction SilentlyContinue
        }
        else {
            Set-Item -Path ("Env:" + $k) -Value $val
        }
    }

    if ($webProc -ne $null -and -not $SkipStartWeb) {
        Write-Info "Stopping web PID $($webProc.Id)"
        try { Stop-Process -Id $webProc.Id -Force -ErrorAction SilentlyContinue } catch { }
    }

    if ($backendProc -ne $null -and -not $SkipStartBackend) {
        Write-Info "Stopping backend PID $($backendProc.Id)"
        try { Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue } catch { }
    }
}
