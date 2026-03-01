export {};

declare global {
  type UpdateStatus = "idle" | "checking" | "available" | "downloading" | "downloaded" | "error";

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

  interface Window {
    electronAPI?: {
      getBackendUrl: () => Promise<string>;
      isElectron: boolean;
      platform: string;

      getUpdateState?: () => Promise<UpdateState>;
      onUpdateAvailable: (cb: (version: string) => void) => (() => void) | void;
      onUpdateProgress: (cb: (progress: UpdateProgress) => void) => (() => void) | void;
      onUpdateDownloaded: (cb: (version: string) => void) => (() => void) | void;
      onUpdateError: (cb: (message: string) => void) => (() => void) | void;
      installUpdate: () => Promise<void>;
    };
  }
}
