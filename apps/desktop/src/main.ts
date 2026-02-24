import { app, BrowserWindow, shell, Menu, ipcMain, utilityProcess } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as http from 'http';
import { accessSync, appendFileSync, mkdirSync, existsSync, renameSync, cpSync } from 'fs';

// ─── State ──────────────────────────────────────────────────────────────────
let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcess | null = null;
let nextProcess: any = null;

const BACKEND_PORT = 8000;
const FRONTEND_PORT = 3000;
const LOOPBACK_HOST = '127.0.0.1';

const isDev = process.env.NODE_ENV === 'development';
const isDebug = process.env.VH_DEBUG === '1';

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
        safeLog('main', 'Starting services...');

        try {
            await startBackend();
            safeLog('main', `✅ Backend ready on port ${BACKEND_PORT}`);

            await startFrontend();
            safeLog('main', `✅ Frontend ready on port ${FRONTEND_PORT}`);

            createWindow();
        } catch (error: any) {
            safeLog('main', `Failed to start services: ${error.message}`, true);
            createWindow();
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
function waitForService(port: number, maxAttempts = 30, urlPath = '/'): Promise<void> {
    return new Promise((resolve, reject) => {
        let attempts = 0;
        const check = () => {
            attempts++;
            const req = http.get(
                {
                    hostname: LOOPBACK_HOST,
                    port,
                    path: urlPath,
                    timeout: 2000,
                },
                (res) => {
                if (res.statusCode && res.statusCode < 500) {
                    resolve();
                } else {
                    retry();
                }
                }
            );
            req.on('error', retry);
            req.on('timeout', () => {
                req.destroy();
                retry();
            });
        };
        const retry = () => {
            if (attempts >= maxAttempts) {
                reject(new Error(`Service on port ${port} did not start after ${maxAttempts} attempts`));
                return;
            }
            setTimeout(check, 1000);
        };
        check();
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
        childEnv.PATH = `${internalDir};${process.env.PATH ?? ''}`;
        backendProcess = spawn(exePath, [], {
            cwd: backendDir,
            env: childEnv,
            stdio: 'pipe',
        });

        backendProcess.stdout?.on('data', (d) => safeLog('backend', d));
        backendProcess.stderr?.on('data', (d) => safeLog('backend', d, true));
        backendProcess.on('error', reject);

        waitForService(BACKEND_PORT, 30, '/api/v1/health').then(resolve).catch(reject);
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

    const url = `http://${LOOPBACK_HOST}:${FRONTEND_PORT}/`;
    safeLog('renderer', `loadURL ${url}`);
    mainWindow.loadURL(url);
    if (isDev || isDebug) mainWindow.webContents.openDevTools();

    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        if (url.startsWith('http://localhost') || url.startsWith(`http://${LOOPBACK_HOST}`)) return { action: 'allow' };
        shell.openExternal(url);
        return { action: 'deny' };
    });

    mainWindow.on('closed', () => { mainWindow = null; });
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
