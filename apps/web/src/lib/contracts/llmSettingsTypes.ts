// LLM Settings 类型定义（对齐 api.md Section 6 契约）

// 模型信息
export type Model = {
    modelId: string;
    displayName: string;
    isCustom?: boolean;
};

// Provider 信息（来自 catalog）
export type Provider = {
    providerId: string;
    displayName: string;
    hasKey: boolean;
    secretUpdatedAtMs?: number;
    models: Model[];
    isCustom?: boolean;
};

// Catalog 响应
export type CatalogResponse = {
    providers: Provider[];
    updatedAtMs: number;
};

// Active 设置响应（可能为空）
export type ActiveSettingsResponse = {
    providerId: string;
    modelId: string;
    hasKey: boolean;
    updatedAtMs: number;
} | null;

// 更新 Active 设置请求
export type UpdateActiveRequest = {
    providerId: string;
    modelId: string;
};

// Provider Secret 请求
export type SecretRequest = {
    apiKey: string;
};

// 测试连接响应
export type TestResponse = {
    ok: boolean;
    latencyMs?: number;
};

// 通用成功响应
export type OkResponse = {
    ok: boolean;
};

// ─── 自定义 model / provider 请求 ────────────────────────────────────────────

export type AddCustomModelRequest = {
    modelId: string;
    displayName: string;
};

export type AddCustomProviderRequest = {
    providerId: string;
    displayName: string;
    baseUrl: string;
    modelId: string;
    modelDisplayName: string;
};
