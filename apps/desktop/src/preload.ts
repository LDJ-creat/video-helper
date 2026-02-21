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
}

const electronAPI: ElectronAPI = {
    isElectron: true,
    platform: process.platform,

    getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
};

// Expose to renderer under window.electronAPI
contextBridge.exposeInMainWorld('electronAPI', electronAPI);
