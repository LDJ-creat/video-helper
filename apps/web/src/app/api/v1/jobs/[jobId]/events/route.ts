export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

function getBackendBaseUrl(): string | null {
  return (
    process.env.API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    // Dev fallback: match services/core/main.py default port
    "http://127.0.0.1:8000"
  );
}

export async function GET(
  request: Request,
  context: { params: Promise<{ jobId: string }> }
): Promise<Response> {
  const { jobId } = await context.params;
  const baseUrl = getBackendBaseUrl();
  if (!baseUrl) {
    return new Response("Missing API_BASE_URL / NEXT_PUBLIC_API_BASE_URL", {
      status: 500,
    });
  }

  const incomingUrl = new URL(request.url);
  const backendUrl = new URL(`/api/v1/jobs/${encodeURIComponent(jobId)}/events`, baseUrl);
  backendUrl.search = incomingUrl.search;

  const headers = new Headers();
  headers.set("Accept", "text/event-stream");
  headers.set("Cache-Control", "no-cache");
  headers.set("Accept-Encoding", "identity");

  const lastEventId = request.headers.get("last-event-id") || request.headers.get("Last-Event-ID");
  if (lastEventId) headers.set("Last-Event-ID", lastEventId);

  // NOTE: keepalive / streaming; disable any caching
  const abortController = new AbortController();
  request.signal.addEventListener("abort", () => abortController.abort(), {
    once: true,
  });

  const upstream = await fetch(backendUrl.toString(), {
    method: "GET",
    headers,
    cache: "no-store",
    signal: abortController.signal,
  });

  if (!upstream.body) {
    return new Response("Upstream SSE has no body", { status: 502 });
  }

  const outHeaders = new Headers(upstream.headers);
  outHeaders.set("Content-Type", "text/event-stream; charset=utf-8");
  outHeaders.set("Cache-Control", "no-cache");
  outHeaders.set("Connection", "keep-alive");
  outHeaders.set("X-Accel-Buffering", "no");

  const { readable, writable } = new TransformStream();
  upstream.body
    .pipeTo(writable)
    .catch(() => {
      // Client disconnected or upstream closed; best-effort.
    });

  return new Response(readable, { status: upstream.status, headers: outHeaders });
}
