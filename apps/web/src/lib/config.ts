function computeApiBaseUrl(): string {
  const publicBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

  // In the browser context:
  if (typeof window !== "undefined") {
    // When running inside Electron, the app is loaded from http://localhost:3000
    // and the backend is at http://localhost:8000. We can directly use the
    // configured URL (or fall back to the default backend port).
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    if ((window as any).electronAPI?.isElectron) {
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
