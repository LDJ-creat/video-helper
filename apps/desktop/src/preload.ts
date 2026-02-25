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
    /** Called when a new version is found and download begins */
    onUpdateAvailable: (cb: (version: string) => void) => void;
    /** Called periodically with download progress percentage (0-100) */
    onUpdateProgress: (cb: (percent: number) => void) => void;
    /** Called when download is complete and ready to install */
    onUpdateDownloaded: (cb: (version: string) => void) => void;
    /** Called if an update error occurs */
    onUpdateError: (cb: (message: string) => void) => void;
    /** Quit the app and install the downloaded update */
    installUpdate: () => Promise<void>;
}

const electronAPI: ElectronAPI = {
    isElectron: true,
    platform: process.platform,

    getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),

    // Forward update events from main process to renderer
    onUpdateAvailable: (cb) => ipcRenderer.on('update-available', (_e, version) => cb(version)),
    onUpdateProgress: (cb) => ipcRenderer.on('update-progress', (_e, percent) => cb(percent)),
    onUpdateDownloaded: (cb) => ipcRenderer.on('update-downloaded', (_e, version) => cb(version)),
    onUpdateError: (cb) => ipcRenderer.on('update-error', (_e, message) => cb(message)),

    installUpdate: () => ipcRenderer.invoke('install-update'),
};

// Expose to renderer under window.electronAPI
contextBridge.exposeInMainWorld('electronAPI', electronAPI);
