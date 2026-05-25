import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type {
    CatalogResponse,
    ActiveSettingsResponse,
    UpdateActiveRequest,
    SecretRequest,
    TestResponse,
    OkResponse,
    AddCustomModelRequest,
    AddCustomProviderRequest,
    RemoteModelsResponse,
} from "../contracts/llmSettingsTypes";
import { config } from "../config";

// Fetch provider catalog
export async function fetchLlmCatalog(): Promise<CatalogResponse> {
    const url = `${config.apiBaseUrl}${endpoints.llmCatalog()}`;
    return apiFetch<CatalogResponse>(url);
}

// Fetch active LLM settings
export async function fetchActiveLlmSettings(): Promise<ActiveSettingsResponse> {
    const url = `${config.apiBaseUrl}${endpoints.llmActive()}`;
    return apiFetch<ActiveSettingsResponse>(url);
}

// Update active LLM settings
export async function updateActiveLlmSettings(request: UpdateActiveRequest): Promise<OkResponse> {
    const url = `${config.apiBaseUrl}${endpoints.llmActive()}`;
    return apiFetch<OkResponse>(url, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
    });
}

// Update provider secret (API key)
export async function updateProviderSecret(providerId: string, apiKey: string): Promise<OkResponse> {
    const request: SecretRequest = { apiKey };
    const url = `${config.apiBaseUrl}${endpoints.llmProviderSecret(providerId)}`;
    return apiFetch<OkResponse>(url, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
    });
}

// Delete provider secret
export async function deleteProviderSecret(providerId: string): Promise<OkResponse> {
    const url = `${config.apiBaseUrl}${endpoints.llmProviderSecret(providerId)}`;
    return apiFetch<OkResponse>(url, {
        method: "DELETE",
    });
}

// Test active LLM settings
export async function testActiveLlmSettings(): Promise<TestResponse> {
    const url = `${config.apiBaseUrl}${endpoints.llmTest()}`;
    return apiFetch<TestResponse>(url, {
        method: "POST",
    });
}

// Test a specific provider + model without changing active settings
export async function testProviderLlmSettings(providerId: string, modelId: string): Promise<TestResponse> {
    const url = `${config.apiBaseUrl}${endpoints.llmProviderTest(providerId)}`;
    return apiFetch<TestResponse>(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ modelId }),
    });
}

export async function fetchRemoteLlmModels(providerId: string): Promise<RemoteModelsResponse> {
    const url = `${config.apiBaseUrl}${endpoints.llmRemoteModels(providerId)}`;
    return apiFetch<RemoteModelsResponse>(url);
}

// ─── Custom models ────────────────────────────────────────────────────────────

export async function addCustomModel(
    providerId: string,
    request: AddCustomModelRequest,
): Promise<OkResponse> {
    const url = `${config.apiBaseUrl}${endpoints.llmProviderModels(providerId)}`;
    return apiFetch<OkResponse>(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
}

export async function deleteCustomModel(
    providerId: string,
    modelId: string,
): Promise<OkResponse> {
    const url = `${config.apiBaseUrl}${endpoints.llmProviderModel(providerId, modelId)}`;
    return apiFetch<OkResponse>(url, {
        method: "DELETE",
    });
}

// ─── Custom providers ─────────────────────────────────────────────────────────

export async function addCustomProvider(
    request: AddCustomProviderRequest,
): Promise<OkResponse> {
    const url = `${config.apiBaseUrl}${endpoints.llmCustomProviders()}`;
    return apiFetch<OkResponse>(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
}

export async function deleteCustomProvider(providerId: string): Promise<OkResponse> {
    const url = `${config.apiBaseUrl}${endpoints.llmCustomProvider(providerId)}`;
    return apiFetch<OkResponse>(url, {
        method: "DELETE",
    });
}
