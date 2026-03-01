/**
 * Health check types aligned with backend /api/v1/health.
 */

export type DependencyPayload = {
    ok: boolean;
    version: string | null;
    message: string | null;
    actions: string[];
};

export type HealthStatus = "ok" | "degraded" | (string & {});

export type HealthCheck = {
    status: HealthStatus;
    ready: boolean;
    tsMs: number;
    dependencies: {
        ffmpeg: DependencyPayload;
        ytDlp: DependencyPayload;
    };
};
