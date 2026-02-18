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
    // Editing endpoints (aligned with api.md Section 4)
    saveContentBlocks: (projectId: string) => `${API_V1}/projects/${projectId}/results/latest/content-blocks`,
    saveMindmap: (projectId: string) => `${API_V1}/projects/${projectId}/results/latest/mindmap`,
    editBlock: (projectId: string, blockId: string) => `${API_V1}/projects/${projectId}/results/latest/blocks/${blockId}`,
    updateHighlightKeyframe: (projectId: string, highlightId: string) => `${API_V1}/projects/${projectId}/results/latest/highlights/${highlightId}/keyframe`,
    uploadAsset: (projectId: string) => `${API_V1}/projects/${projectId}/assets`,
    // Search endpoints
    search: () => `${API_V1}/search`,
    // Settings endpoints (legacy analyze settings)
    settingsAnalyze: () => `${API_V1}/settings/analyze`,
    // LLM Settings endpoints (vNext per api.md Section 6)
    llmCatalog: () => `${API_V1}/settings/llm/catalog`,
    llmActive: () => `${API_V1}/settings/llm/active`,
    llmProviderSecret: (providerId: string) => `${API_V1}/settings/llm/providers/${providerId}/secret`,
    llmTest: () => `${API_V1}/settings/llm/active/test`,
    // AI Features
    chat: () => `${API_V1}/chat/completions`,
    chatSessions: (projectId: string) => `${API_V1}/chat/sessions?projectId=${projectId}`,
    chatSessionMessages: (sessionId: string) => `${API_V1}/chat/sessions/${sessionId}/messages`,
    quizGenerate: () => `${API_V1}/quiz/generate`,
    quizSave: () => `${API_V1}/quiz/save`,
    quizSessions: (projectId: string) => `${API_V1}/quiz/sessions?projectId=${projectId}`,
    quizSession: (sessionId: string) => `${API_V1}/quiz/sessions/${sessionId}`,
};

