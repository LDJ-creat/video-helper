function computeApiBaseUrl(): string {
  const publicBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

  // In the browser context:
  if (typeof window !== "undefined") {
    // When running inside Electron desktop, the app is loaded from
    // http://127.0.0.1:3000 and the backend is at http://127.0.0.1:8000.
    // IMPORTANT: In CI/release builds, NEXT_PUBLIC_* values may be empty at
    // build-time, so we must have a safe default even without .env.local.
    // Also: preload/bridge can fail in some packaging scenarios, so do not
    // rely solely on window.electronAPI for Electron detection.
    const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const hasBridge = Boolean((window as any).electronAPI?.isElectron);
    const isElectronUa = /\bElectron\b/i.test(ua);
    if (hasBridge || isElectronUa) {
      return publicBaseUrl || "http://127.0.0.1:8000";
    }

    // In a regular browser, prefer same-origin requests so Next.js rewrites
    // can proxy to the backend (avoids CORS issues).
    try {
      if (publicBaseUrl) {
        const u = new URL(publicBaseUrl);
        if (u.origin === window.location.origin) return publicBaseUrl;
      }
    } catch {
      // ignore invalid URL
    }
    return "";
  }

  // On the server (SSR), use the configured public base URL.
  return publicBaseUrl;
}

export const config = {
  apiBaseUrl: computeApiBaseUrl(),
};
