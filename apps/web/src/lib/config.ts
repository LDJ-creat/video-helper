function computeApiBaseUrl(): string {
  const publicBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

  // In the browser, prefer same-origin requests (so Next.js rewrites can proxy
  // to the backend). This avoids CORS issues across browsers/devices.
  if (typeof window !== "undefined") {
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

  // On the server, keep the configured public base URL (if any).
  return publicBaseUrl;
}

export const config = {
  apiBaseUrl: computeApiBaseUrl(),
};
