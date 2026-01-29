export type ApiErrorEnvelope = {
  error: {
    code: string;
    message: string;
    details?: unknown;
    requestId?: string;
  };
};

export async function apiFetch<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);

  if (response.ok) {
    return (await response.json()) as T;
  }

  let body: unknown = undefined;
  try {
    body = await response.json();
  } catch {
    // ignore
  }

  throw body ?? new Error(`HTTP ${response.status}`);
}
