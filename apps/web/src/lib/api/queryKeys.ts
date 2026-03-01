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
  // LLM Settings query keys
  llmCatalog: ["llm", "catalog"] as const,
  llmActive: ["llm", "active"] as const,
  // AI Feature keys
  chatSessions: (projectId: string) => ["chat", "sessions", projectId] as const,
  chatMessages: (sessionId: string) => ["chat", "messages", sessionId] as const,
  // Quiz Feature keys
  quizSessions: (projectId: string) => ["quiz", "sessions", projectId] as const,
  quizDetail: (sessionId: string) => ["quiz", "detail", sessionId] as const,
  // Settings
  settings: ["settings"] as const,
};
