export const queryKeys = {
  health: ["health"] as const,
  projects: ["projects"] as const,
  project: (projectId: string) => ["projects", projectId] as const,
  jobs: ["jobs"] as const,
  job: (jobId: string) => ["jobs", jobId] as const,
  logs: (jobId: string) => ["jobs", jobId, "logs"] as const,
};
