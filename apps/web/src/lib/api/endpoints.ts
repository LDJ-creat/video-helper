export const API_V1 = "/api/v1";

export const endpoints = {
    job: (jobId: string) => `${API_V1}/jobs/${jobId}`,
    jobEvents: (jobId: string) => `${API_V1}/jobs/${jobId}/events`,
    jobLogs: (jobId: string) => `${API_V1}/jobs/${jobId}/logs`,
    jobCancel: (jobId: string) => `${API_V1}/jobs/${jobId}/cancel`,
    jobRetry: (jobId: string) => `${API_V1}/jobs/${jobId}/retry`,
};
