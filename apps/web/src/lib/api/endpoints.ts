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
    // Notes endpoints   
    // Content Blocks endpoints
    saveContentBlocks: (projectId: string, resultId: string) => `${API_V1}/projects/${projectId}/results/latest/content-blocks`,
    // Mindmap endpoints
    saveMindmap: (projectId: string, resultId: string) => `${API_V1}/projects/${projectId}/results/${resultId}/mindmap`,
    // Search endpoints
    search: () => `${API_V1}/search`,
    // LLM Settings endpoints (vNext per api.md Section 6)
    llmCatalog: () => `${API_V1}/settings/llm/catalog`,
    llmActive: () => `${API_V1}/settings/llm/active`,
    llmProviderSecret: (providerId: string) => `${API_V1}/settings/llm/providers/${providerId}/secret`,
    llmTest: () => `${API_V1}/settings/llm/active/test`,
};
