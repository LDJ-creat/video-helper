export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function normalizeBaseUrl(url: string): string {
  return url.replace(/\/+$/, "");
}

export async function POST(req: Request): Promise<Response> {
  const apiBaseUrl = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!apiBaseUrl) {
    return new Response(
      JSON.stringify({
        error: "API_BASE_URL (or NEXT_PUBLIC_API_BASE_URL) is not set",
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }

  const upstreamUrl = `${normalizeBaseUrl(apiBaseUrl)}/api/v1/chat/completions`;

  // Preserve raw body to avoid any subtle JSON/string differences
  const bodyText = await req.text();

  const upstreamResp = await fetch(upstreamUrl, {
    method: "POST",
    headers: {
      "Content-Type": req.headers.get("content-type") || "application/json",
      Accept: "text/event-stream",
    },
    body: bodyText,
    cache: "no-store",
  });

  const headers = new Headers(upstreamResp.headers);

  // Ensure streaming-friendly headers; remove length so Node can stream chunks.
  headers.set("Cache-Control", "no-cache");
  headers.set("Connection", "keep-alive");
  headers.set("X-Accel-Buffering", "no");
  headers.delete("Content-Length");

  return new Response(upstreamResp.body, {
    status: upstreamResp.status,
    headers,
  });
}
