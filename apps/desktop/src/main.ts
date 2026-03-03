import { app, BrowserWindow, shell, Menu, ipcMain, utilityProcess, dialog } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as http from 'http';
import { accessSync, appendFileSync, mkdirSync, existsSync, renameSync, cpSync, readdirSync } from 'fs';
import { autoUpdater } from 'electron-updater';

// ─── State ──────────────────────────────────────────────────────────────────
let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcess | null = null;
let nextProcess: any = null;

type UpdateStatus = 'idle' | 'checking' | 'available' | 'downloading' | 'downloaded' | 'error';
type UpdateProgress = {
    percent: number;
    transferred: number;
    total: number;
    bytesPerSecond?: number;
};
type UpdateState = {
    status: UpdateStatus;
    version?: string;
    progress?: UpdateProgress;
    error?: string;
};

let updateState: UpdateState = { status: 'idle' };

const BACKEND_PORT = 8000;
const FRONTEND_PORT = 3000;
const LOOPBACK_HOST = '127.0.0.1';

const isDev = process.env.NODE_ENV === 'development';
const isDebug = process.env.VH_DEBUG === '1';

// CI runners (especially macOS) may crash during Chromium GPU initialization.
// Disable hardware acceleration early (must be before app.whenReady()).
const shouldDisableGpu =
    (process.env.CI || '').toLowerCase() === 'true' ||
    process.env.VH_DISABLE_GPU === '1' ||
    process.argv.includes('--disable-gpu');

if (shouldDisableGpu) {
    try {
        app.disableHardwareAcceleration();
        // Prefer software rendering paths.
        app.commandLine.appendSwitch('disable-gpu');
        app.commandLine.appendSwitch('disable-gpu-compositing');
        // swiftshader is the most reliable fallback in headless CI.
        app.commandLine.appendSwitch('use-gl', 'swiftshader');
        // Reduce crashy surface area in CI.
        app.commandLine.appendSwitch('disable-gpu-shader-disk-cache');
        app.commandLine.appendSwitch('disable-gpu-sandbox');
    } catch {
        // ignore
    }
}

// ─── userData Path (Production) ─────────────────────────────────────────────
// Default userData on Windows is %APPDATA%/<appName>. Our package name is
// "desktop" (not user-friendly). Use a stable, recognizable folder name.
function configureUserDataPath() {
    if (isDev) return;

    const desiredBaseName = 'video-helper';

    // Capture current default path before overriding.
    const oldUserData = app.getPath('userData');
    const appData = app.getPath('appData');
    const newUserData = path.join(appData, desiredBaseName);

    if (oldUserData === newUserData) return;

    try {
        app.setPath('userData', newUserData);
    } catch {
        // If setPath fails, fall back to default.
        return;
    }

    // Best-effort migrate existing DATA_DIR to the new location.
    const oldDataDir = path.join(oldUserData, 'data');
    const newDataDir = path.join(newUserData, 'data');
    try {
        if (existsSync(oldDataDir) && !existsSync(newDataDir)) {
            mkdirSync(newUserData, { recursive: true });
            try {
                renameSync(oldDataDir, newDataDir);
            } catch {
                // Fallback to copy (keep old data in place if rename fails).
                cpSync(oldDataDir, newDataDir, { recursive: true });
            }
        }
    } catch {
        // ignore migration failures
    }
}

configureUserDataPath();

process.on('uncaughtException', (err) => {
    safeLog('main', `uncaughtException: ${err?.stack ?? err}`, true);
});

process.on('unhandledRejection', (reason) => {
    safeLog('main', `unhandledRejection: ${String(reason)}`, true);
});

// ─── Single Instance Lock ────────────────────────────────────────────────────
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
    app.quit();
} else {
    app.on('second-instance', () => {
        if (mainWindow) {
            if (mainWindow.isMinimized()) mainWindow.restore();
            mainWindow.focus();
        }
    });

    // ─── App Lifecycle ───────────────────────────────────────────────────────
    app.whenReady().then(async () => {
        buildApplicationMenu();
        safeLog('main', `appName=${app.getName()}`);
        safeLog('main', `userData=${app.getPath('userData')}`);
        safeLog('main', `dataDir=${path.join(app.getPath('userData'), 'data')}`);

        // Open window immediately to show loading screen
        createWindow();
        initAutoUpdater();

        safeLog('main', 'Starting services...');

        try {
            await startBackend();
            safeLog('main', `✅ Backend ready on port ${BACKEND_PORT}`);

            await startFrontend();
            safeLog('main', `✅ Frontend ready on port ${FRONTEND_PORT}`);

            navigateToApp();
        } catch (error: any) {
            safeLog('main', `Failed to start services: ${error.message}`, true);
            showErrorPage(error.message);
        }
    });

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });

    app.on('before-quit', () => {
        shutdownSubprocesses();
    });

    app.on('window-all-closed', () => {
        if (process.platform !== 'darwin') {
            shutdownSubprocesses();
            app.quit();
        }
    });
}

// ─── Logging ─────────────────────────────────────────────────────────────────
function safeLog(source: string, data: any, isError = false) {
    const message = `[${source}] ${data.toString().trim()}`;
    try {
        if (isError) {
            console.error(message);
        } else {
            console.log(message);
        }
    } catch (err) {
        // Silent catch for EPIPE
    }

    // In production (Explorer launch has no console), also log to file.
    if (!isDev) {
        try {
            const logDir = path.join(app.getPath('userData'), 'logs');
            mkdirSync(logDir, { recursive: true });
            const logFile = path.join(logDir, 'desktop.log');
            appendFileSync(logFile, `${new Date().toISOString()} ${message}\n`);
        } catch {
            // ignore logging failures
        }
    }
}

// ─── Path Helpers ────────────────────────────────────────────────────────────
function getResourcesPath(): string {
    if (isDev) {
        return path.join(__dirname, '..', '..', '..');
    }
    return process.resourcesPath;
}

function getBackendExePath(): string {
    if (isDev) {
        return path.join(getResourcesPath(), 'services', 'core');
    }
    const platform = process.platform;
    const exeName = platform === 'win32' ? 'backend.exe' : 'backend';
    return path.join(getResourcesPath(), 'backend', exeName);
}

// ─── Health Check ────────────────────────────────────────────────────────────
function waitForService(
    port: number,
    maxAttempts = 30,
    urlPath = '/',
    initialDelayMs = 0,
): Promise<void> {
    return new Promise((resolve, reject) => {
        let attempts = 0;
        const check = () => {
            attempts++;
            let settled = false;
            const req = http.get(
                {
                    hostname: LOOPBACK_HOST,
                    port,
                    path: urlPath,
                    // Total request timeout: destroy the socket if no response within 3 s.
                    timeout: 3000,
                },
                (res) => {
                    if (!settled) {
                        settled = true;
                        // Drain to free the socket, then decide.
                        res.resume();
                        if (res.statusCode && res.statusCode < 500) {
                            resolve();
                        } else {
                            retry();
                        }
                    }
                }
            );
            req.on('error', () => { if (!settled) { settled = true; retry(); } });
            req.on('timeout', () => { if (!settled) { settled = true; req.destroy(); retry(); } });
        };
        const retry = () => {
            if (attempts >= maxAttempts) {
                reject(new Error(`Service on port ${port} did not start after ${maxAttempts} attempts`));
                return;
            }
            setTimeout(check, 1000);
        };
        // For packaged backends (PyInstaller), the process cold-start can take
        // several seconds before the socket is even open. Skip early polls that
        // are guaranteed to fail and burn retry budget.
        if (initialDelayMs > 0) {
            setTimeout(check, initialDelayMs);
        } else {
            check();
        }
    });
}

// ─── Backend Process ─────────────────────────────────────────────────────────
function startBackend(): Promise<void> {
    return new Promise((resolve, reject) => {
        if (isDev) {
            safeLog('main', 'Dev mode: checking backend...');
            waitForService(BACKEND_PORT, 3, '/api/v1/health').then(resolve).catch(() => {
                startBackendFromSource().then(resolve).catch(reject);
            });
            return;
        }

        const exePath = getBackendExePath();
        const backendDir = path.dirname(exePath);
        const internalDir = path.join(backendDir, '_internal');
        const dataDir = path.join(app.getPath('userData'), 'data');

        // PyInstaller bootloader can be confused by externally-set Python env vars
        // (common on dev machines with Conda/Python tooling). Ensure the packaged
        // backend uses its own bundled stdlib.
        const childEnv: Record<string, string> = { ...process.env } as any;
        for (const k of [
            'PYTHONHOME',
            'PYTHONPATH',
            'PYTHONSAFEPATH',
            'PYTHONSTARTUP',
            'PYTHONNOUSERSITE',
        ]) {
            if (k in childEnv) {
                delete childEnv[k];
            }
        }
        // Prefer safety: avoid user-site injecting unexpected modules.
        childEnv.PYTHONNOUSERSITE = '1';

        childEnv.PORT = String(BACKEND_PORT);
        childEnv.DATA_DIR = dataDir;
        // Prefer packaged native deps over system/conda PATH.
        childEnv.PATH = `${internalDir}${path.delimiter}${process.env.PATH ?? ''}`;
        backendProcess = spawn(exePath, [], {
            cwd: backendDir,
            env: childEnv,
            stdio: 'pipe',
        });

        backendProcess.stdout?.on('data', (d) => safeLog('backend', d));
        backendProcess.stderr?.on('data', (d) => safeLog('backend', d, true));
        backendProcess.on('error', reject);

        // Give PyInstaller backend a generous head-start before polling.
        // On slow machines / with Windows Defender scanning, unpacking can take 10+ s.
        waitForService(BACKEND_PORT, 60, '/api/v1/health', 5000).then(resolve).catch(reject);
    });
}

function startBackendFromSource(): Promise<void> {
    return new Promise((resolve, reject) => {
        const coreDir = path.join(getResourcesPath(), 'services', 'core');
        const uvPath = process.platform === 'win32' ? 'uv.exe' : 'uv';
        backendProcess = spawn(uvPath, ['run', 'python', 'main.py'], {
            cwd: coreDir,
            env: { ...process.env },
            stdio: 'pipe',
            shell: true,
        });

        backendProcess.stdout?.on('data', (d) => safeLog('backend', d));
        backendProcess.stderr?.on('data', (d) => safeLog('backend', d, true));
        backendProcess.on('error', reject);

        waitForService(BACKEND_PORT, 30, '/api/v1/health').then(resolve).catch(reject);
    });
}

// ─── Frontend Process ─────────────────────────────────────────────────────────
function startFrontend(): Promise<void> {
    return new Promise((resolve, reject) => {
        if (isDev) {
            waitForService(FRONTEND_PORT, 3, '/').then(resolve).catch(() => {
                startNextJsDev().then(resolve).catch(reject);
            });
            return;
        }

        const standaloneServerCandidates = [
            path.join(getResourcesPath(), 'web', 'apps', 'web', 'server.js'),
            path.join(getResourcesPath(), 'web', 'server.js'),
        ];
        const standaloneServer = standaloneServerCandidates.find((candidate) => {
            try {
                accessSync(candidate);
                return true;
            } catch {
                return false;
            }
        });

        if (!standaloneServer) {
            reject(new Error(`Next standalone server not found. Tried: ${standaloneServerCandidates.join(', ')}`));
            return;
        }

        // Sanity check: ensure transitive deps that Next expects are actually present
        // in the packaged standalone output (common failure mode with pnpm layouts).
        try {
            const serverDir = path.dirname(standaloneServer);
            const styledJsxRootPkg = path.join(serverDir, 'node_modules', 'styled-jsx', 'package.json');
            const styledJsxNestedPkg = path.join(serverDir, 'node_modules', 'next', 'node_modules', 'styled-jsx', 'package.json');
            if (!existsSync(styledJsxRootPkg) && !existsSync(styledJsxNestedPkg)) {
                let nodeModulesPreview = '';
                try {
                    const nmDir = path.join(serverDir, 'node_modules');
                    const entries = readdirSync(nmDir, { withFileTypes: true })
                        .filter((e) => e.isDirectory())
                        .map((e) => e.name)
                        .slice(0, 50);
                    nodeModulesPreview = entries.join(', ');
                } catch {
                    // ignore
                }
                reject(
                    new Error(
                        `Next standalone is missing styled-jsx at runtime. ` +
                        `Tried: ${styledJsxRootPkg} and ${styledJsxNestedPkg}. ` +
                        `node_modules preview: [${nodeModulesPreview}]`
                    )
                );
                return;
            }
        } catch {
            // ignore
        }

        nextProcess = utilityProcess.fork(standaloneServer, [], {
            cwd: path.dirname(standaloneServer),
            env: {
                ...process.env,
                NODE_ENV: 'production',
                PORT: String(FRONTEND_PORT),
                HOSTNAME: LOOPBACK_HOST,
                NEXT_PUBLIC_API_BASE_URL: `http://${LOOPBACK_HOST}:${BACKEND_PORT}`,
            },
            stdio: 'pipe',
        });

        nextProcess.stdout?.on('data', (d: Buffer) => safeLog('frontend', d));
        nextProcess.stderr?.on('data', (d: Buffer) => safeLog('frontend', d, true));
        nextProcess.on('error', reject);

        waitForService(FRONTEND_PORT, 60, '/').then(resolve).catch(reject);
    });
}

function startNextJsDev(): Promise<void> {
    return new Promise((resolve, reject) => {
        const webDir = path.join(getResourcesPath(), 'apps', 'web');
        nextProcess = spawn('pnpm', ['dev'], {
            cwd: webDir,
            env: { ...process.env, NEXT_PUBLIC_API_BASE_URL: `http://${LOOPBACK_HOST}:${BACKEND_PORT}` },
            stdio: 'pipe',
            shell: true,
        });

        nextProcess.stdout?.on('data', (d: Buffer) => safeLog('frontend', d));
        nextProcess.stderr?.on('data', (d: Buffer) => safeLog('frontend', d, true));
        nextProcess.on('error', reject);

        waitForService(FRONTEND_PORT, 60, '/').then(resolve).catch(reject);
    });
}

// ─── Window ───────────────────────────────────────────────────────────────────
function createWindow(): void {
    mainWindow = new BrowserWindow({
        width: 1440, height: 900,
        minWidth: 1024, minHeight: 600,
        title: 'Video Helper',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            webSecurity: true,
        },
        ...(isDev ? {} : { autoHideMenuBar: true }),
    });

    safeLog('renderer', 'BrowserWindow created');

    mainWindow.webContents.on('did-start-loading', () => {
        safeLog('renderer', 'did-start-loading');
    });

    mainWindow.webContents.on('dom-ready', () => {
        safeLog('renderer', 'dom-ready');
    });

    mainWindow.webContents.on('did-finish-load', () => {
        safeLog('renderer', `did-finish-load url=${mainWindow?.webContents.getURL() ?? ''}`);
    });

    mainWindow.webContents.on('did-stop-loading', () => {
        safeLog('renderer', 'did-stop-loading');
    });

    mainWindow.webContents.on('did-navigate', (_event, url) => {
        safeLog('renderer', `did-navigate ${url}`);
    });

    mainWindow.webContents.on('did-navigate-in-page', (_event, url, isMainFrame) => {
        safeLog('renderer', `did-navigate-in-page mainFrame=${isMainFrame} ${url}`);
    });

    mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
        // level: 0=log, 1=warn, 2=error
        const lvl = level === 2 ? 'error' : level === 1 ? 'warn' : 'log';
        safeLog('renderer', `console.${lvl} ${sourceId}:${line} ${message}`, level === 2);
    });

    mainWindow.webContents.on('render-process-gone', (_event, details) => {
        safeLog('renderer', `render-process-gone reason=${details.reason} exitCode=${details.exitCode}`, true);
    });

    mainWindow.webContents.on('unresponsive', () => {
        safeLog('renderer', 'unresponsive', true);
    });

    mainWindow.webContents.on('responsive', () => {
        safeLog('renderer', 'responsive');
    });

    mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
        safeLog('renderer', `did-fail-load ${errorCode} ${errorDescription} ${validatedURL}`, true);
    });

    safeLog('renderer', 'load loading page');
    mainWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(getLoadingHtml()));
    if (isDev || isDebug) mainWindow.webContents.openDevTools();

    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        if (url.startsWith('http://localhost') || url.startsWith(`http://${LOOPBACK_HOST}`)) return { action: 'allow' };
        shell.openExternal(url);
        return { action: 'deny' };
    });

    mainWindow.on('closed', () => { mainWindow = null; });
}

function navigateToApp(): void {
    if (!mainWindow) return;
    const url = `http://${LOOPBACK_HOST}:${FRONTEND_PORT}/`;
    safeLog('renderer', `navigateToApp URL: ${url}`);
    mainWindow.loadURL(url);
}

function showErrorPage(errorMsg: string): void {
    if (!mainWindow) return;
    safeLog('renderer', 'show error page');
    mainWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(getErrorHtml(errorMsg)));
}

function getLoadingHtml(): string {
    return `
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>Video Helper - 正在启动</title>
    <style>
        body { margin: 0; background: #09090b; color: #fafafa; font-family: system-ui, -apple-system, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
        .spinner { border: 3px solid rgba(255, 255, 255, 0.1); border-top-color: #fafafa; border-radius: 50%; width: 32px; height: 32px; animation: spin 1s linear infinite; margin-bottom: 24px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        h1 { margin: 0 0 8px 0; font-size: 24px; font-weight: 500; letter-spacing: -0.025em; }
        p { margin: 0; color: #a1a1aa; font-size: 14px; }
    </style>
</head>
<body>
    <div class="spinner"></div>
    <h1>Video Helper</h1>
    <p>正在启动服务，请稍候...</p>
</body>
</html>
    `.trim();
}

function getErrorHtml(errorMsg: string): string {
    return `
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>Video Helper - 启动失败</title>
    <style>
        body { margin: 0; background: #09090b; color: #fafafa; font-family: system-ui, -apple-system, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }
        .icon { width: 48px; height: 48px; min-width: 48px; background: rgba(239, 68, 68, 0.1); color: #ef4444; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: bold; margin-bottom: 24px; }
        h1 { margin: 0 0 12px 0; font-size: 24px; font-weight: 500; letter-spacing: -0.025em; }
        .error { background: #18181b; border: 1px solid #27272a; padding: 16px; border-radius: 8px; color: #ef4444; font-size: 14px; font-family: monospace; max-width: 600px; word-break: break-all; margin-bottom: 32px; }
        .btn { background: #fafafa; color: #18181b; border: none; padding: 10px 24px; border-radius: 6px; font-size: 14px; font-weight: 500; cursor: pointer; transition: opacity 0.2s; }
        .btn:hover { opacity: 0.9; }
    </style>
</head>
<body>
    <div class="icon">!</div>
    <h1>启动失败</h1>
    <div class="error">${errorMsg}</div>
    <button class="btn" id="retryBtn">重试 / 重启应用</button>
    <script>
      document.getElementById('retryBtn').addEventListener('click', () => {
         if (window.electronAPI && window.electronAPI.relaunchApp) {
           window.electronAPI.relaunchApp();
         }
      });
    </script>
</body>
</html>
    `.trim();
}

function buildApplicationMenu(): void {
    if (!isDev) Menu.setApplicationMenu(null);
}

// ─── Graceful Shutdown ────────────────────────────────────────────────────────
function shutdownSubprocesses(): void {
    const kill = (proc: any, name: string) => {
        if (!proc) return;
        try {
            if (proc.kill) {
                if (process.platform === 'win32' && name === 'backend') {
                    spawn('taskkill', ['/pid', String(proc.pid), '/f', '/t']);
                } else {
                    proc.kill();
                }
            }
        } catch (e: any) {
            safeLog('main', `Failed to kill ${name}: ${e.message}`, true);
        }
    };

    kill(backendProcess, 'backend');
    kill(nextProcess, 'frontend');
}

// ─── IPC ─────────────────────────────────────────────────────────────────────
ipcMain.handle('get-backend-url', () => `http://${LOOPBACK_HOST}:${BACKEND_PORT}`);
ipcMain.handle('install-update', () => autoUpdater.quitAndInstall());
ipcMain.handle('get-update-state', () => updateState);
ipcMain.handle('relaunch-app', () => {
    shutdownSubprocesses();
    app.relaunch();
    app.exit(0);
});

// ─── Auto Updater ─────────────────────────────────────────────────────────────
function initAutoUpdater(): void {
    if (isDev || isDebug || process.env.CI === 'true' || process.env.VH_DISABLE_UPDATER === '1') {
        safeLog('updater', 'Dev mode: skipping auto-update check');
        return;
    }

    // Configure logging
    // Our CI currently creates GitHub prereleases. Allow prerelease updates so
    // users can receive fixes without manual uninstall/reinstall.
    autoUpdater.allowPrerelease = true;
    autoUpdater.autoDownload = false;
    autoUpdater.autoInstallOnAppQuit = true;

    autoUpdater.on('checking-for-update', () => {
        safeLog('updater', 'Checking for updates...');
        updateState = { status: 'checking' };
    });

    autoUpdater.on('update-available', (info) => {
        safeLog('updater', `Update available: ${info.version}`);
        updateState = { status: 'available', version: info.version };
        mainWindow?.webContents.send('update-available', info.version);
        // Start download automatically after notifying the renderer
        autoUpdater.downloadUpdate();
    });

    autoUpdater.on('update-not-available', (info) => {
        safeLog('updater', `No update available. Current version: ${info.version}`);
        updateState = { status: 'idle', version: info.version };
    });

    autoUpdater.on('download-progress', (progress) => {
        const percent = Number.isFinite(progress.percent) ? Number(progress.percent.toFixed(1)) : 0;
        const payload: UpdateProgress = {
            percent,
            transferred: progress.transferred,
            total: progress.total,
            bytesPerSecond: progress.bytesPerSecond,
        };
        updateState = {
            status: 'downloading',
            version: updateState.version,
            progress: payload,
        };
        safeLog(
            'updater',
            `Download progress: ${percent}% (${Math.round(progress.transferred / 1024)}KB / ${Math.round(progress.total / 1024)}KB)`,
        );
        mainWindow?.webContents.send('update-progress', payload);
    });

    autoUpdater.on('update-downloaded', (info) => {
        safeLog('updater', `Update downloaded: ${info.version}. Ready to install.`);
        updateState = { status: 'downloaded', version: info.version };
        mainWindow?.webContents.send('update-downloaded', info.version);

        // If the renderer is blank/crashed, still allow the user to finish update.
        // Use a native dialog from the main process.
        dialog
            .showMessageBox({
                type: 'info',
                title: 'Video Helper 更新已就绪',
                message: `已下载更新版本 ${info.version}`,
                detail: '是否现在重启并安装更新？',
                buttons: ['立即重启安装', '稍后'],
                defaultId: 0,
                cancelId: 1,
                noLink: true,
            })
            .then((r) => {
                if (r.response === 0) {
                    autoUpdater.quitAndInstall();
                }
            })
            .catch(() => {
                // ignore dialog failures
            });
    });

    autoUpdater.on('error', (err) => {
        safeLog('updater', `Update error: ${err.message}`, true);
        updateState = { status: 'error', version: updateState.version, error: err.message };
        mainWindow?.webContents.send('update-error', err.message);
    });

    // Delay check by 5 seconds so it doesn't interfere with app startup
    setTimeout(() => {
        autoUpdater.checkForUpdates().catch((err) => {
            safeLog('updater', `checkForUpdates failed: ${err.message}`, true);
        });
    }, 5000);
}
