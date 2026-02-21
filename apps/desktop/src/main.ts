import { app, BrowserWindow, shell, Menu, ipcMain } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as http from 'http';

// ─── State ──────────────────────────────────────────────────────────────────
let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcess | null = null;
let nextProcess: ChildProcess | null = null;

const BACKEND_PORT = 8000;
const FRONTEND_PORT = 3000;

const isDev = process.env.NODE_ENV === 'development';

// ─── Path Helpers ────────────────────────────────────────────────────────────
function getResourcesPath(): string {
    if (isDev) {
        return path.join(__dirname, '..', '..', '..'); // project root in dev
    }
    return process.resourcesPath;
}

function getBackendExePath(): string {
    if (isDev) {
        // In dev, we assume the python backend is running separately on port 8000
        // or we can spawn it from source
        return path.join(getResourcesPath(), 'services', 'core');
    }
    // In production, the bundled backend exe is in resources/backend/
    const platform = process.platform;
    const exeName = platform === 'win32' ? 'backend.exe' : 'backend';
    return path.join(getResourcesPath(), 'backend', exeName);
}

// ─── Health Check ────────────────────────────────────────────────────────────
function waitForService(port: number, maxAttempts = 30): Promise<void> {
    return new Promise((resolve, reject) => {
        let attempts = 0;
        const check = () => {
            attempts++;
            const req = http.get(`http://localhost:${port}`, (res) => {
                if (res.statusCode && res.statusCode < 500) {
                    resolve();
                } else {
                    retry();
                }
            });
            req.on('error', retry);
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
            // In dev mode, assume FastAPI is started manually or via docker
            // Just check if it's already running
            console.log('[main] Dev mode: checking if backend is already running...');
            waitForService(BACKEND_PORT, 3)
                .then(resolve)
                .catch(() => {
                    console.log('[main] Backend not running. Attempting to start from source...');
                    startBackendFromSource().then(resolve).catch(reject);
                });
            return;
        }

        // Production: spawn the bundled executable
        const exePath = getBackendExePath();
        console.log(`[main] Starting backend executable: ${exePath}`);
        backendProcess = spawn(exePath, [], {
            env: {
                ...process.env,
                PORT: String(BACKEND_PORT),
            },
            stdio: 'pipe',
        });

        backendProcess.stdout?.on('data', (d) => console.log('[backend]', d.toString().trim()));
        backendProcess.stderr?.on('data', (d) => console.error('[backend]', d.toString().trim()));
        backendProcess.on('error', reject);

        waitForService(BACKEND_PORT).then(resolve).catch(reject);
    });
}

function startBackendFromSource(): Promise<void> {
    return new Promise((resolve, reject) => {
        const coreDir = path.join(getResourcesPath(), 'services', 'core');
        console.log(`[main] Starting FastAPI from source in: ${coreDir}`);

        // Try uv first, then python
        const uvPath = process.platform === 'win32' ? 'uv.exe' : 'uv';
        backendProcess = spawn(uvPath, ['run', 'python', 'main.py'], {
            cwd: coreDir,
            env: { ...process.env },
            stdio: 'pipe',
            shell: true,
        });

        backendProcess.stdout?.on('data', (d) => console.log('[backend]', d.toString().trim()));
        backendProcess.stderr?.on('data', (d) => console.error('[backend]', d.toString().trim()));
        backendProcess.on('error', (err) => {
            console.error('[main] Failed to start backend:', err);
            reject(err);
        });

        waitForService(BACKEND_PORT).then(resolve).catch(reject);
    });
}

// ─── Frontend Process ─────────────────────────────────────────────────────────
function startFrontend(): Promise<void> {
    return new Promise((resolve, reject) => {
        if (isDev) {
            // In dev mode, assume Next.js dev server is already running
            console.log('[main] Dev mode: checking if Next.js dev server is running...');
            waitForService(FRONTEND_PORT, 3)
                .then(resolve)
                .catch(() => {
                    console.log('[main] Next.js dev server not running. Starting it...');
                    startNextJsDev().then(resolve).catch(reject);
                });
            return;
        }

        // Production: start Next.js standalone server
        const standaloneServer = path.join(getResourcesPath(), 'web', 'server.js');
        console.log(`[main] Starting Next.js standalone server: ${standaloneServer}`);

        nextProcess = spawn(process.execPath, [standaloneServer], {
            env: {
                ...process.env,
                NODE_ENV: 'production',
                PORT: String(FRONTEND_PORT),
                NEXT_PUBLIC_API_BASE_URL: `http://localhost:${BACKEND_PORT}`,
            },
            stdio: 'pipe',
        });

        nextProcess.stdout?.on('data', (d) => console.log('[frontend]', d.toString().trim()));
        nextProcess.stderr?.on('data', (d) => console.error('[frontend]', d.toString().trim()));
        nextProcess.on('error', reject);

        waitForService(FRONTEND_PORT).then(resolve).catch(reject);
    });
}

function startNextJsDev(): Promise<void> {
    return new Promise((resolve, reject) => {
        const webDir = path.join(getResourcesPath(), 'apps', 'web');
        console.log(`[main] Starting Next.js dev server in: ${webDir}`);

        nextProcess = spawn('pnpm', ['dev'], {
            cwd: webDir,
            env: {
                ...process.env,
                NEXT_PUBLIC_API_BASE_URL: `http://localhost:${BACKEND_PORT}`,
            },
            stdio: 'pipe',
            shell: true,
        });

        nextProcess.stdout?.on('data', (d) => console.log('[frontend]', d.toString().trim()));
        nextProcess.stderr?.on('data', (d) => console.error('[frontend]', d.toString().trim()));
        nextProcess.on('error', reject);

        waitForService(FRONTEND_PORT, 60).then(resolve).catch(reject);
    });
}

// ─── Window ───────────────────────────────────────────────────────────────────
function createWindow(): void {
    mainWindow = new BrowserWindow({
        width: 1440,
        height: 900,
        minWidth: 1024,
        minHeight: 600,
        title: 'Video Helper',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            // Allow loading local resources (for video files)
            webSecurity: true,
        },
        // Remove default menu in production
        ...(isDev ? {} : { autoHideMenuBar: true }),
    });

    // Load application
    mainWindow.loadURL(`http://localhost:${FRONTEND_PORT}`);

    // Open DevTools in dev mode
    if (isDev) {
        mainWindow.webContents.openDevTools();
    }

    // Open external links in default browser
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        if (url.startsWith('http://localhost')) {
            return { action: 'allow' };
        }
        shell.openExternal(url);
        return { action: 'deny' };
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

function buildApplicationMenu(): void {
    if (!isDev) {
        Menu.setApplicationMenu(null);
    }
}

// ─── Graceful Shutdown ────────────────────────────────────────────────────────
function shutdownSubprocesses(): void {
    console.log('[main] Shutting down subprocesses...');

    const kill = (proc: ChildProcess | null, name: string) => {
        if (!proc) return;
        try {
            if (process.platform === 'win32') {
                spawn('taskkill', ['/pid', String(proc.pid), '/f', '/t']);
            } else {
                proc.kill('SIGTERM');
            }
            console.log(`[main] Sent termination signal to ${name} (pid=${proc.pid})`);
        } catch (e) {
            console.error(`[main] Failed to kill ${name}:`, e);
        }
    };

    kill(backendProcess, 'backend');
    kill(nextProcess, 'frontend');
}

// ─── App Lifecycle ────────────────────────────────────────────────────────────

// Register IPC handlers before app is ready
ipcMain.handle('get-backend-url', () => {
    return `http://localhost:${BACKEND_PORT}`;
});

app.whenReady().then(async () => {
    buildApplicationMenu();

    console.log('[main] Starting services...');

    try {
        // Start backend first
        await startBackend();
        console.log(`[main] ✅ Backend ready on port ${BACKEND_PORT}`);

        // Start frontend
        await startFrontend();
        console.log(`[main] ✅ Frontend ready on port ${FRONTEND_PORT}`);

        // Create window after both services are ready
        createWindow();
    } catch (error) {
        console.error('[main] Failed to start services:', error);
        // Still create window so user can see error / use basic UI
        createWindow();
    }

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
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
