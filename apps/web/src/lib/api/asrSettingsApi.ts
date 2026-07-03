import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type {
    AsrActiveSettingsResponse,
    AsrCatalogResponse,
    AsrRemoteModelsResponse,
    AsrSecretRequest,
    AsrTestResponse,
    AddCustomAsrModelRequest,
    OkResponse,
    UpdateAsrActiveRequest,
} from "../contracts/asrSettingsTypes";
import { config } from "../config";

export async function fetchAsrCatalog(): Promise<AsrCatalogResponse> {
    return apiFetch<AsrCatalogResponse>(`${config.apiBaseUrl}${endpoints.asrCatalog()}`);
}

export async function fetchActiveAsrSettings(): Promise<AsrActiveSettingsResponse> {
    return apiFetch<AsrActiveSettingsResponse>(`${config.apiBaseUrl}${endpoints.asrActive()}`);
}

export async function updateActiveAsrSettings(request: UpdateAsrActiveRequest): Promise<OkResponse> {
    return apiFetch<OkResponse>(`${config.apiBaseUrl}${endpoints.asrActive()}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
}

export async function updateAsrProviderSecret(providerId: string, apiKey: string): Promise<OkResponse> {
    const request: AsrSecretRequest = { apiKey };
    return apiFetch<OkResponse>(`${config.apiBaseUrl}${endpoints.asrProviderSecret(providerId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
}

export async function deleteAsrProviderSecret(providerId: string): Promise<OkResponse> {
    return apiFetch<OkResponse>(`${config.apiBaseUrl}${endpoints.asrProviderSecret(providerId)}`, {
        method: "DELETE",
    });
}

export async function testActiveAsrSettings(): Promise<AsrTestResponse> {
    return apiFetch<AsrTestResponse>(`${config.apiBaseUrl}${endpoints.asrTest()}`, {
        method: "POST",
    });
}

export async function testAsrProviderSettings(providerId: string, modelId: string): Promise<AsrTestResponse> {
    return apiFetch<AsrTestResponse>(`${config.apiBaseUrl}${endpoints.asrProviderTest(providerId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ modelId }),
    });
}

export async function fetchAsrRemoteModels(providerId: string): Promise<AsrRemoteModelsResponse> {
    return apiFetch<AsrRemoteModelsResponse>(`${config.apiBaseUrl}${endpoints.asrRemoteModels(providerId)}`);
}

export async function addCustomAsrModel(providerId: string, request: AddCustomAsrModelRequest): Promise<OkResponse> {
    return apiFetch<OkResponse>(`${config.apiBaseUrl}${endpoints.asrProviderModels(providerId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
}

export async function deleteCustomAsrModel(providerId: string, modelId: string): Promise<OkResponse> {
    return apiFetch<OkResponse>(`${config.apiBaseUrl}${endpoints.asrProviderModel(providerId, modelId)}`, {
        method: "DELETE",
    });
}

export async function prefetchAsrModel(modelSize?: string): Promise<OkResponse> {
    return apiFetch<OkResponse>(`${config.apiBaseUrl}${endpoints.asrPrefetch()}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ modelSize: modelSize ?? "base" }),
    });
}
