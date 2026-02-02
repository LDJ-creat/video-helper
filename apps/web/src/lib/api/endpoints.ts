export const API_V1 = "/api/v1";

export const endpoints = {
    health: () => `${API_V1}/health`,
    projects: () => `${API_V1}/projects`,
    project: (projectId: string) => `${API_V1}/projects/${projectId}`,
    deleteProject: (projectId: string) => `${API_V1}/projects/${projectId}`,
    jobs: () => `${API_V1}/jobs`,
    job: (jobId: string) => `${API_V1}/jobs/${jobId}`,
    jobEvents: (jobId: string) => `${API_V1}/jobs/${jobId}/events`,
    jobLogs: (jobId: string) => `${API_V1}/jobs/${jobId}/logs`,
    jobCancel: (jobId: string) => `${API_V1}/jobs/${jobId}/cancel`,
    jobRetry: (jobId: string) => `${API_V1}/jobs/${jobId}/retry`,
    // Results & Assets endpoints
    resultLatest: (projectId: string) => `${API_V1}/projects/${projectId}/results/latest`,
    asset: (assetId: string) => `${API_V1}/assets/${assetId}`,
    assetContent: (assetId: string) => `${API_V1}/assets/${assetId}/content`,
};
