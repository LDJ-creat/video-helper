#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Video Helper Desktop — 全流程生产打包脚本 (Windows)

.DESCRIPTION
    依次执行：
      Step 1: 编译 Electron TypeScript 主进程
      Step 2: 打包 Next.js 前端 (standalone)
      Step 3: 打包 FastAPI 后端 (PyInstaller)
      Step 4: 打包 Electron 安装包 (electron-builder NSIS)

.EXAMPLE
    # 从项目根目录运行:
    powershell -ExecutionPolicy Bypass -File apps\desktop\scripts\build-all.ps1
#>

$ErrorActionPreference = "Stop"
$ROOT = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$DESKTOP = Join-Path $ROOT "apps\desktop"
$WEB = Join-Path $ROOT "apps\web"
$CORE = Join-Path $ROOT "services\core"

function Write-Step($n, $msg) {
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "  Step ${n}: $msg" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
}

function Invoke-Step($cmd, $dir) {
    Push-Location $dir
    try {
        Invoke-Expression $cmd
        if ($LASTEXITCODE -ne 0) { throw "Command failed: $cmd" }
    }
    finally {
        Pop-Location
    }
}

function Get-LatestInstaller($outDir) {
    if (-not (Test-Path $outDir)) { return $null }
    $candidates = Get-ChildItem -Path $outDir -Filter "Video Helper Setup *.exe" -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending
    return ($candidates | Select-Object -First 1)
}

function Stop-DesktopAppIfRunning() {
    Write-Host "Stopping running Video Helper related processes..." -ForegroundColor Yellow

    # Most reliable on Windows: kill by image name + whole tree.
    $imageNames = @(
        "Video Helper.exe",
        "backend.exe",
        "electron.exe",
        "app-builder.exe"
    )

    foreach ($img in $imageNames) {
        try {
            & taskkill /IM $img /F /T 2>$null | Out-Null
        }
        catch {
            # ignore
        }
    }

    # Extra guard: kill any process running from our build output dirs.
    $pathLike = @(
        "*\\apps\\desktop\\release\\win-unpacked\\*",
        "*\\apps\\desktop\\release-temp*\\win-unpacked\\*"
    )

    $pathProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $exe = $_.ExecutablePath
        $cmd = $_.CommandLine
        ($exe -and ($pathLike | Where-Object { $exe -like $_ })) -or
        ($cmd -and ($pathLike | Where-Object { $cmd -like $_ }))
    }

    foreach ($proc in $pathProcs) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        }
        catch {
            # ignore
        }
    }

    Start-Sleep -Milliseconds 800
}

function Clear-StaleWinUnpacked() {
    $targets = @()

    # Default output directory.
    $targets += (Join-Path $DESKTOP "release\win-unpacked")

    # Any previous temp outputs (release-temp, release-temp3, release-temp4, ...)
    $tempDirs = @(Get-ChildItem -Path $DESKTOP -Directory -Filter "release-temp*" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    foreach ($d in $tempDirs) {
        $targets += (Join-Path $d "win-unpacked")
    }

    $targets = $targets | Select-Object -Unique

    function Try-RemoveDir($p) {
        if (-not (Test-Path $p)) { return $true }
        try {
            Remove-Item -Recurse -Force $p -ErrorAction Stop
        }
        catch {
            try {
                & cmd.exe /c "rmdir /s /q \"$p\"" 2>$null | Out-Null
            }
            catch {
                # ignore
            }
        }
        return (-not (Test-Path $p))
    }

    foreach ($target in $targets) {
        if (-not (Test-Path $target)) { continue }

        Write-Host "Cleaning stale output: $target" -ForegroundColor Yellow

        $maxRetries = 10
        for ($i = 1; $i -le $maxRetries; $i++) {
            if (Try-RemoveDir $target) { break }

            if ($i -lt $maxRetries) {
                # In practice, locks come from a still-running unpacked app.
                if ($i -eq 3) { Stop-DesktopAppIfRunning }
                Start-Sleep -Milliseconds 900
            }
        }

        if (Test-Path $target) {
            Write-Host "WARN: Failed to clean stale output: $target" -ForegroundColor Yellow
            Write-Host "      A process is still holding a file handle (common culprits: Video Helper, Explorer preview pane, antivirus, VS Code watchers)." -ForegroundColor Yellow
            Write-Host "      Tip: resmon.exe -> CPU -> Associated Handles -> search for 'win-unpacked' or 'app.asar'." -ForegroundColor Yellow
            return $false
        }
    }

    return $true
}

function Stop-NextStandaloneIfRunning() {
    Write-Host "Stopping processes that may lock Next standalone output..." -ForegroundColor Yellow

    # Kill common dev/build processes (best-effort).
    $imageNames = @(
        "node.exe",
        "pnpm.exe",
        "npm.exe",
        "yarn.exe"
    )

    # Only kill node/pnpm processes that clearly reference our web standalone output.
    $lockPathLike = @(
        "*\\apps\\web\\.next\\standalone\\*",
        "*\\apps\\web\\.next\\*"
    )

    $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $cmd = $_.CommandLine
        $exe = $_.ExecutablePath
        ($cmd -and ($lockPathLike | Where-Object { $cmd -like $_ })) -or
        ($exe -and ($lockPathLike | Where-Object { $exe -like $_ }))
    }

    foreach ($p in $procs) {
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
        catch {
            # ignore
        }
    }

    # Additionally, if a node process is holding the lock but command line is hidden,
    # we still try a gentle kill-by-name only when a lock was detected above.
    if ($procs -and $procs.Count -gt 0) {
        foreach ($img in $imageNames) {
            try { & taskkill /IM $img /F /T 2>$null | Out-Null } catch { }
        }
    }

    Start-Sleep -Milliseconds 800
}

function Clear-StaleNextStandalone() {
    $target = Join-Path $WEB ".next\standalone"
    if (-not (Test-Path $target)) { return }

    Write-Host "Cleaning stale Next standalone output: $target" -ForegroundColor Yellow

    function Try-RemoveDir($p) {
        if (-not (Test-Path $p)) { return $true }
        try {
            Remove-Item -Recurse -Force $p -ErrorAction Stop
        }
        catch {
            # Fallback: cmd.exe sometimes succeeds when PowerShell fails.
            try {
                & cmd.exe /c "rmdir /s /q \"$p\"" 2>$null | Out-Null
            }
            catch {
                # ignore
            }
        }
        return (-not (Test-Path $p))
    }

    $maxRetries = 10
    for ($i = 1; $i -le $maxRetries; $i++) {
        if (Try-RemoveDir $target) { break }

        if ($i -lt $maxRetries) {
            if ($i -eq 2) { Stop-NextStandaloneIfRunning }
            if ($i -eq 4) { Stop-DesktopAppIfRunning }
            Start-Sleep -Milliseconds 900
        }
    }

    if (Test-Path $target) {
        throw "Failed to clean stale Next standalone output: $target. A process is still holding a file handle (common culprits: Video Helper, node.exe/Next, VS Code file watchers, Explorer preview pane, antivirus).\n\nTo identify the locker: open Resource Monitor (resmon.exe) -> CPU -> Associated Handles -> search for 'standalone' and kill the shown process. Then re-run this script."
    }
}

function Ensure-StaticFfmpeg() {
    # Download static single-file ffmpeg/ffprobe binaries into _ci/ffmpeg and
    # prepend it to PATH for the rest of this script.
    $dir = Join-Path $ROOT "_ci\ffmpeg"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    $ffmpegExe = Join-Path $dir "ffmpeg.exe"
    $ffprobeExe = Join-Path $dir "ffprobe.exe"

    $base = "https://github.com/eugeneware/ffmpeg-static/releases/latest/download"
    $ffmpegUrl = "${base}/ffmpeg-win32-x64"
    $ffprobeUrl = "${base}/ffprobe-win32-x64"

    function Download-WithRetry($url, $outFile) {
        $max = 3
        for ($i = 1; $i -le $max; $i++) {
            try {
                Write-Host "Downloading $url -> $outFile (attempt ${i}/${max})" -ForegroundColor Cyan
                Invoke-WebRequest -Uri $url -OutFile $outFile
                if (-not (Test-Path -LiteralPath $outFile)) { throw "Download produced no file: $outFile" }
                return
            }
            catch {
                if ($i -eq $max) { throw }
                Start-Sleep -Seconds (2 * $i)
            }
        }
    }

    if (-not (Test-Path -LiteralPath $ffmpegExe)) {
        Download-WithRetry $ffmpegUrl $ffmpegExe
    }
    if (-not (Test-Path -LiteralPath $ffprobeExe)) {
        Download-WithRetry $ffprobeUrl $ffprobeExe
    }

    # Prepend to PATH so build_backend.py can pick it up.
    $env:Path = "${dir};$env:Path"

    try {
        & $ffmpegExe -version | Select-Object -First 1
        & $ffprobeExe -version | Select-Object -First 1
    }
    catch {
        throw "ffmpeg/ffprobe sanity check failed: $($_.Exception.Message)"
    }
}

# ─── Step 1: Compile Electron TypeScript ──────────────────────────────────────
Write-Step 1 "Compiling Electron main process (TypeScript)"
Invoke-Step "pnpm compile" $DESKTOP

# ─── Step 2: Build Next.js Standalone ─────────────────────────────────────────
Write-Step 2 "Building Next.js frontend (standalone)"
Stop-DesktopAppIfRunning
Stop-NextStandaloneIfRunning
Clear-StaleNextStandalone
$env:BUILD_STANDALONE = "1"
$env:API_BASE_URL = "http://127.0.0.1:8000"
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
Invoke-Step "pnpm build" $WEB
Remove-Item Env:BUILD_STANDALONE -ErrorAction SilentlyContinue
Remove-Item Env:API_BASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:NEXT_PUBLIC_API_BASE_URL -ErrorAction SilentlyContinue

# Next standalone output + pnpm workspace may produce a non-resolvable node_modules
# layout under `.next/standalone` (only `.pnpm/` is present). For packaged desktop
# apps we need a classic node_modules inside `.next/standalone/apps/web`.
Write-Host "Hydrating Next standalone node_modules (npm)" -ForegroundColor Cyan
$standaloneWeb = Join-Path $WEB ".next\standalone\apps\web"
if (-not (Test-Path $standaloneWeb)) {
    throw "Next standalone output not found at: $standaloneWeb. Did Step 2 (pnpm build) succeed?"
}

Push-Location $standaloneWeb
try {
    $env:npm_config_progress = "false"
    # Ensure we don't keep a pnpm-style/symlinked node_modules produced by Next standalone output.
    $standaloneNodeModules = Join-Path $standaloneWeb "node_modules"
    if (Test-Path $standaloneNodeModules) {
        try { Remove-Item -Recurse -Force $standaloneNodeModules -ErrorAction Stop } catch { }
        if (Test-Path $standaloneNodeModules) {
            try { & cmd.exe /c "rmdir /s /q \"$standaloneNodeModules\"" 2>$null | Out-Null } catch { }
        }
    }
    & npm install --omit=dev --no-package-lock --loglevel=error
    if ($LASTEXITCODE -ne 0) { throw "npm install failed in $standaloneWeb" }

    $checkScript = Join-Path $ROOT "scripts\ci\check-next-standalone-deps.mjs"
    & node $checkScript $standaloneWeb
    if ($LASTEXITCODE -ne 0) {
        throw "Sanity check failed: styled-jsx is not resolvable for Next runtime in standalone output: $standaloneWeb"
    }
}
finally {
    Pop-Location
    Remove-Item Env:npm_config_progress -ErrorAction SilentlyContinue
}

# Remove root standalone node_modules (pnpm virtual store) to avoid shipping a large,
# non-resolvable tree. Runtime starts from `apps/web/server.js` so it is not needed.
$rootStandaloneNodeModules = Join-Path $WEB ".next\standalone\node_modules"
if (Test-Path $rootStandaloneNodeModules) {
    try {
        Remove-Item -Recurse -Force $rootStandaloneNodeModules -ErrorAction Stop
    }
    catch {
        try {
            & cmd.exe /c "rmdir /s /q \"$rootStandaloneNodeModules\"" 2>$null | Out-Null
        }
        catch {
            # ignore
        }
    }
}

# ─── Step 3: PyInstaller Backend ──────────────────────────────────────────────
Write-Step 3 "Packaging FastAPI backend (PyInstaller)"
Ensure-StaticFfmpeg
Invoke-Step "uv run python scripts\build_backend.py" $CORE

# ─── Step 4: electron-builder ─────────────────────────────────────────────────
Write-Step 4 "Building Electron installer (electron-builder)"
Stop-DesktopAppIfRunning
$cleanOk = Clear-StaleWinUnpacked
$outputDir = $null
if ($cleanOk) {
    $outputDir = Join-Path $DESKTOP "release"
    Invoke-Step "pnpm build" $DESKTOP
}
else {
    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    $altOut = "release-temp-$ts"
    Write-Host "\nwin-unpacked is locked; building with a fresh output directory: $altOut" -ForegroundColor Yellow
    Write-Host "(This avoids app.asar locks from previous runs. You can delete old release/win-unpacked later.)\n" -ForegroundColor Yellow
    $outputDir = Join-Path $DESKTOP $altOut
    Invoke-Step "pnpm exec electron-builder --config.directories.output=$altOut" $DESKTOP
}

# Normalize: always place a copy in apps/desktop/release for easy discovery.
try {
    $releaseDir = Join-Path $DESKTOP "release"
    if (-not (Test-Path $releaseDir)) { New-Item -ItemType Directory -Path $releaseDir | Out-Null }

    $installer = Get-LatestInstaller $outputDir
    if ($installer) {
        Copy-Item -Force -Path $installer.FullName -Destination (Join-Path $releaseDir $installer.Name)
        Write-Host "Installer written: $($installer.FullName)" -ForegroundColor Green
        Write-Host "Installer copied to: $(Join-Path $releaseDir $installer.Name)" -ForegroundColor Green
    }
    else {
        Write-Host "WARN: Could not locate installer under: $outputDir" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "WARN: Failed to copy installer into release/: $($_.Exception.Message)" -ForegroundColor Yellow
}

# ─── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✅  Build complete!                             ║" -ForegroundColor Green
Write-Host "║                                                  ║" -ForegroundColor Green
Write-Host "║  Installer: apps\desktop\release\                ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Green
