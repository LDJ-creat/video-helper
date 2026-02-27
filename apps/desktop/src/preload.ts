import { contextBridge, ipcRenderer } from 'electron';

/**
 * Preload script - runs in renderer context with limited Node.js access.
 * Exposes a minimal, typed API to the renderer (Next.js) via contextBridge.
 *
 * Security: Only expose what is explicitly needed. No raw ipcRenderer access.
 */

export interface ElectronAPI {
    /** Get the backend API base URL (resolved by main process) */
    getBackendUrl: () => Promise<string>;
    /** Check if running inside Electron */
    isElectron: boolean;
    /** Platform identifier */
    platform: string;

    // ── Auto-update ──────────────────────────────────────────────────────────
    /** Current update state (best-effort snapshot from main process) */
    getUpdateState: () => Promise<UpdateState>;
    /** Called when a new version is found and download begins */
    onUpdateAvailable: (cb: (version: string) => void) => () => void;
    /** Called periodically with download progress */
    onUpdateProgress: (cb: (progress: UpdateProgress) => void) => () => void;
    /** Called when download is complete and ready to install */
    onUpdateDownloaded: (cb: (version: string) => void) => () => void;
    /** Called if an update error occurs */
    onUpdateError: (cb: (message: string) => void) => () => void;
    /** Quit the app and install the downloaded update */
    installUpdate: () => Promise<void>;
    /** Relaunch the entire app (used by error page retry button) */
    relaunchApp: () => Promise<void>;
}

export type UpdateStatus = 'idle' | 'checking' | 'available' | 'downloading' | 'downloaded' | 'error';

export type UpdateProgress = {
    percent: number;
    transferred: number;
    total: number;
    bytesPerSecond?: number;
};

export type UpdateState = {
    status: UpdateStatus;
    version?: string;
    progress?: UpdateProgress;
    error?: string;
};

const electronAPI: ElectronAPI = {
    isElectron: true,
    platform: process.platform,

    getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
    getUpdateState: () => ipcRenderer.invoke('get-update-state'),

    // Forward update events from main process to renderer
    onUpdateAvailable: (cb) => {
        const listener = (_e: unknown, version: string) => cb(version);
        ipcRenderer.on('update-available', listener);
        return () => ipcRenderer.removeListener('update-available', listener);
    },
    onUpdateProgress: (cb) => {
        const listener = (_e: unknown, progress: UpdateProgress) => cb(progress);
        ipcRenderer.on('update-progress', listener);
        return () => ipcRenderer.removeListener('update-progress', listener);
    },
    onUpdateDownloaded: (cb) => {
        const listener = (_e: unknown, version: string) => cb(version);
        ipcRenderer.on('update-downloaded', listener);
        return () => ipcRenderer.removeListener('update-downloaded', listener);
    },
    onUpdateError: (cb) => {
        const listener = (_e: unknown, message: string) => cb(message);
        ipcRenderer.on('update-error', listener);
        return () => ipcRenderer.removeListener('update-error', listener);
    },

    installUpdate: () => ipcRenderer.invoke('install-update'),
    relaunchApp: () => ipcRenderer.invoke('relaunch-app'),
};

// Expose to renderer under window.electronAPI
contextBridge.exposeInMainWorld('electronAPI', electronAPI);
