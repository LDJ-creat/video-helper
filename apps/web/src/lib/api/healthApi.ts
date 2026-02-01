import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type { HealthCheck } from "../contracts/healthTypes";
import { config } from "../config";

/**
 * Fetch health check status from backend
 * @returns Health check response with dependency status
 */
export async function fetchHealth(): Promise<HealthCheck> {
    const url = `${config.apiBaseUrl}${endpoints.health()}`;
    return apiFetch<HealthCheck>(url);
}
