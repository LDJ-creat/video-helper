/** Dev-only logging for ingest category prefill. Filter console by `[ingest:category]`. */
export function logIngestCategory(
  step: string,
  data: Record<string, unknown>
): void {
  if (process.env.NODE_ENV !== "development") return;
  console.debug(`[ingest:category] ${step}`, data);
}
