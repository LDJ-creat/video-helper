/**
 * Health check types aligned with API contract
 * Reference: api.md health endpoint specification
 */

export type DependencyStatus = "available" | "missing" | "error";

export type DependencyCheck = {
    status: DependencyStatus;
    version?: string;
    message?: string;
};

export type HealthCheck = {
    status: "healthy" | "degraded" | "unhealthy";
    dependencies: {
        ffmpeg: DependencyCheck;
        ytdlp: DependencyCheck;
        whisper: DependencyCheck;
    };
    timestamp: number;
};
