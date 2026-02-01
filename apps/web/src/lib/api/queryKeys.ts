export const queryKeys = {
  health: ["health"] as const,
  projects: ["projects"] as const,
  jobs: ["jobs"] as const,
  job: (jobId: string) => ["jobs", jobId] as const,
  logs: (jobId: string) => ["jobs", jobId, "logs"] as const,
};
