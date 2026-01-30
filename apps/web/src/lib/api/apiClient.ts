import type { ErrorEnvelope } from "../contracts/errorEnvelope";

export type ApiErrorEnvelope = ErrorEnvelope;

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
