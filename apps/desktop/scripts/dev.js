#!/usr/bin/env node
/**
 * Development startup helper for Video Helper Desktop
 *
 * Usage: node apps/desktop/scripts/dev.js
 *
 * Starts FastAPI + Next.js dev server + Electron.
 * If a service is already running on its port, it is reused (not restarted).
 */

const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const PROJECT_ROOT = path.join(__dirname, '..', '..', '..');
const WEB_DIR = path.join(PROJECT_ROOT, 'apps', 'web');
const BACKEND_DIR = path.join(PROJECT_ROOT, 'services', 'core');

const BACKEND_PORT = 8000;
const FRONTEND_PORT = 3000;

// Track spawned child processes for cleanup
const children = [];

/** Check once if port is responding (no retry). Returns true/false. */
function isPortReady(port) {
    return new Promise((resolve) => {
        const req = http.get({ hostname: 'localhost', port, path: '/', timeout: 2000 }, (res) => {
            resolve(res.statusCode < 500);
        });
        req.on('error', () => resolve(false));
        req.on('timeout', () => { req.destroy(); resolve(false); });
    });
}

/** Wait until port responds (with up to maxMs ms of retries). */
function waitForPort(port, name, maxMs = 90000) {
    return new Promise((resolve, reject) => {
        const start = Date.now();
        const check = () => {
            isPortReady(port).then((ok) => {
                if (ok) {
                    console.log(`✅ ${name} ready on :${port}`);
                    resolve();
                } else if (Date.now() - start > maxMs) {
                    reject(new Error(`${name} did not start within ${maxMs / 1000}s`));
                } else {
                    setTimeout(check, 1000);
                }
            });
        };
        check();
    });
}

/** Spawn a process and track it for cleanup. */
function spawnTracked(cmd, args, opts) {
    const proc = spawn(cmd, args, opts);
    children.push(proc);
    proc.on('error', (err) => console.error(`[${cmd}] spawn error:`, err.message));
    return proc;
}

async function startBackend() {
    const already = await isPortReady(BACKEND_PORT);
    if (already) {
        console.log(`♻️  Backend already running on :${BACKEND_PORT}, reusing.`);
        return;
    }
    console.log('📡 Starting backend (FastAPI)...');
    spawnTracked('uv', ['run', 'python', 'main.py'], {
        cwd: BACKEND_DIR,
        stdio: 'inherit',
        shell: true,
    });
    await waitForPort(BACKEND_PORT, 'Backend');
}

async function startFrontend() {
    const already = await isPortReady(FRONTEND_PORT);
    if (already) {
        console.log(`♻️  Frontend already running on :${FRONTEND_PORT}, reusing.`);
        return;
    }
    console.log('🌐 Starting frontend (Next.js)...');
    spawnTracked('pnpm', ['dev'], {
        cwd: WEB_DIR,
        env: { ...process.env, NEXT_PUBLIC_API_BASE_URL: `http://localhost:${BACKEND_PORT}` },
        stdio: 'inherit',
        shell: true,
    });
    await waitForPort(FRONTEND_PORT, 'Frontend', 120000);
}

function startElectron() {
    console.log('\n🖥️  Launching Electron window...');
    const desktopDir = path.join(PROJECT_ROOT, 'apps', 'desktop');
    const electron = spawnTracked('npx', ['electron', '.'], {
        cwd: desktopDir,
        env: { ...process.env, NODE_ENV: 'development' },
        stdio: 'inherit',
        shell: true,
    });
    return electron;
}

function cleanup() {
    console.log('\n🛑 Shutting down...');
    for (const proc of children) {
        try { proc.kill(); } catch { }
    }
    process.exit(0);
}

async function main() {
    console.log('🚀 Starting Video Helper Desktop (dev mode)...\n');

    // First compile TypeScript main process
    console.log('🔨 Compiling Electron main process...');
    const compile = spawnTracked('pnpm', ['compile'], {
        cwd: path.join(PROJECT_ROOT, 'apps', 'desktop'),
        stdio: 'inherit',
        shell: true,
    });
    await new Promise((resolve, reject) => {
        compile.on('close', (code) => code === 0 ? resolve() : reject(new Error(`tsc failed with code ${code}`)));
    });
    console.log('✅ TypeScript compiled\n');

    try {
        await startBackend();
        await startFrontend();
    } catch (e) {
        console.error('❌ Service startup failed:', e.message);
        cleanup();
        return;
    }

    const electron = startElectron();

    process.on('SIGINT', cleanup);
    process.on('SIGTERM', cleanup);
    electron.on('close', () => {
        console.log('Electron closed, shutting down services...');
        cleanup();
    });
}

main().catch((err) => {
    console.error('Fatal error:', err.message);
    cleanup();
});
