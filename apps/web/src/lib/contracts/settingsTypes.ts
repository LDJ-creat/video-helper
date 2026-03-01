// Settings 相关类型定义（分析/LLM 配置，对齐 api.md 契约）

// Provider 类型（严格按照 api.md）
export type AnalyzeProvider = "llm" | "rules";

// 分析设置（非敏感字段，永不包含 API key）
export type AnalyzeSettings = {
    provider: AnalyzeProvider;
    baseUrl: string | null;           // LLM provider base URL（不含 key）
    model: string | null;
    timeoutS: number;
    allowRulesFallback: boolean;      // 当 LLM 不可用时是否允许 rules fallback
    debug: boolean;                   // 仅输出安全元数据
};

// 读取设置响应（GET /api/v1/settings/analyze）
export type SettingsResponse = AnalyzeSettings;

// 更新设置请求（PUT /api/v1/settings/analyze）
export type UpdateSettingsRequest = {
    provider: AnalyzeProvider;
    baseUrl: string | null;
    model: string | null;
    timeoutS?: number;
    allowRulesFallback?: boolean;
    debug?: boolean;
};
