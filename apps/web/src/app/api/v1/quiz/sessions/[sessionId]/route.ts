export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

function getBackendBaseUrl(): string {
  return (
    process.env.API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    // Dev fallback: match services/core/main.py default port
    "http://127.0.0.1:8000"
  );
}

export async function GET(
  request: Request,
  context: { params: Promise<{ sessionId: string }> }
): Promise<Response> {
  const { sessionId } = await context.params;
  const baseUrl = getBackendBaseUrl();

  const incomingUrl = new URL(request.url);
  const backendUrl = new URL(`/api/v1/quiz/sessions/${encodeURIComponent(sessionId)}`, baseUrl);
  backendUrl.search = incomingUrl.search;

  const upstream = await fetch(backendUrl.toString(), {
    method: "GET",
    headers: {
      Accept: request.headers.get("accept") || "application/json",
    },
    cache: "no-store",
  });

  const headers = new Headers(upstream.headers);
  headers.set("Cache-Control", "no-store");

  return new Response(upstream.body, {
    status: upstream.status,
    headers,
  });
}
