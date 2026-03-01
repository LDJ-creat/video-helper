import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type { SettingsResponse, UpdateSettingsRequest } from "../contracts/settingsTypes";
import { config } from "../config";

export async function fetchSettings(): Promise<SettingsResponse> {
    const url = `${config.apiBaseUrl}${endpoints.settingsAnalyze()}`;
    return apiFetch<SettingsResponse>(url);
}

export async function updateSettings(settings: UpdateSettingsRequest): Promise<SettingsResponse> {
    const url = `${config.apiBaseUrl}${endpoints.settingsAnalyze()}`;
    return apiFetch<SettingsResponse>(url, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(settings),
    });
}
