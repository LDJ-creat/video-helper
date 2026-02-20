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
} from "../contracts/llmSettingsTypes";

// Fetch provider catalog
export async function fetchLlmCatalog(): Promise<CatalogResponse> {
    return apiFetch<CatalogResponse>(endpoints.llmCatalog());
}

// Fetch active LLM settings
export async function fetchActiveLlmSettings(): Promise<ActiveSettingsResponse> {
    return apiFetch<ActiveSettingsResponse>(endpoints.llmActive());
}

// Update active LLM settings
export async function updateActiveLlmSettings(request: UpdateActiveRequest): Promise<OkResponse> {
    return apiFetch<OkResponse>(endpoints.llmActive(), {
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
    return apiFetch<OkResponse>(endpoints.llmProviderSecret(providerId), {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
    });
}

// Delete provider secret
export async function deleteProviderSecret(providerId: string): Promise<OkResponse> {
    return apiFetch<OkResponse>(endpoints.llmProviderSecret(providerId), {
        method: "DELETE",
    });
}

// Test active LLM settings
export async function testActiveLlmSettings(): Promise<TestResponse> {
    return apiFetch<TestResponse>(endpoints.llmTest(), {
        method: "POST",
    });
}

// ─── Custom models ────────────────────────────────────────────────────────────

export async function addCustomModel(
    providerId: string,
    request: AddCustomModelRequest,
): Promise<OkResponse> {
    return apiFetch<OkResponse>(endpoints.llmProviderModels(providerId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
}

export async function deleteCustomModel(
    providerId: string,
    modelId: string,
): Promise<OkResponse> {
    return apiFetch<OkResponse>(endpoints.llmProviderModel(providerId, modelId), {
        method: "DELETE",
    });
}

// ─── Custom providers ─────────────────────────────────────────────────────────

export async function addCustomProvider(
    request: AddCustomProviderRequest,
): Promise<OkResponse> {
    return apiFetch<OkResponse>(endpoints.llmCustomProviders(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
}

export async function deleteCustomProvider(providerId: string): Promise<OkResponse> {
    return apiFetch<OkResponse>(endpoints.llmCustomProvider(providerId), {
        method: "DELETE",
    });
}
