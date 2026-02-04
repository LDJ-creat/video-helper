import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type { SettingsResponse, UpdateSettingsRequest } from "../contracts/settingsTypes";

export async function fetchSettings(): Promise<SettingsResponse> {
    return apiFetch<SettingsResponse>(endpoints.settingsAnalyze());
}

export async function updateSettings(settings: UpdateSettingsRequest): Promise<SettingsResponse> {
    return apiFetch<SettingsResponse>(endpoints.settingsAnalyze(), {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(settings),
    });
}
