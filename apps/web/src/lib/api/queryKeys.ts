export const queryKeys = {
  health: ["health"] as const,
  projects: ["projects"] as const,
  project: (projectId: string) => ["projects", projectId] as const,
  jobs: ["jobs"] as const,
  job: (jobId: string) => ["jobs", jobId] as const,
  logs: (jobId: string) => ["jobs", jobId, "logs"] as const,
  // Results & Assets query keys
  result: (projectId: string) => ["results", projectId] as const,
  asset: (assetId: string) => ["assets", assetId] as const,
  // Search query keys
  search: (query: string) => ["search", query] as const,
  // Settings query keys
  settings: ["settings"] as const,
};
