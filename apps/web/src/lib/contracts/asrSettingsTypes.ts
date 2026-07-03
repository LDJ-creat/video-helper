export type AsrCatalogModel = {
    modelId: string;
    displayName: string;
    description?: string | null;
    isCustom?: boolean;
};

export type AsrRemoteModel = {
    modelId: string;
    displayName: string;
};

export type AsrRemoteModelsResponse = {
    ok: boolean;
    models: AsrRemoteModel[];
    error?: { code: string; message: string } | null;
};

export type AddCustomAsrModelRequest = {
    modelId: string;
    displayName?: string;
};

export type AsrCatalogProvider = {
    providerId: string;
    displayName: string;
    hasKey: boolean;
    secretUpdatedAtMs?: number | null;
    models: AsrCatalogModel[];
    notes?: string | null;
};

export type AsrCatalogResponse = {
    providers: AsrCatalogProvider[];
    updatedAtMs: number;
};

export type AsrActiveSettingsResponse = {
    configured: boolean;
    cloudEnabled: boolean;
    providerId: string | null;
    modelId: string | null;
    localModelSize: string;
    localDevice: string;
    fallbackToLocal: boolean;
    hasKey: boolean;
    updatedAtMs: number | null;
};

export type UpdateAsrActiveRequest = {
    cloudEnabled: boolean;
    providerId: string;
    modelId: string;
    fallbackToLocal?: boolean;
};

export type AsrSecretRequest = {
    apiKey: string;
};

export type AsrTestResponse = {
    ok: boolean;
    latencyMs: number;
    mode?: string | null;
    message?: string | null;
};

export type OkResponse = {
    ok: boolean;
};
