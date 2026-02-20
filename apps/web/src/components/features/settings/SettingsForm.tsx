"use client";

import { useState } from "react";
import {
    useLlmCatalog,
    useActiveLlmSettings,
    useUpdateActiveLlmSettings,
    useUpdateProviderSecret,
    useDeleteProviderSecret,
    useTestActiveLlmSettings,
} from "@/lib/api/llmSettingsQueries";
import type { Provider } from "@/lib/contracts/llmSettingsTypes";

export function SettingsForm() {
    const { data: catalog, isLoading: catalogLoading, isError: catalogError } = useLlmCatalog();
    const { data: activeSettings, isLoading: activeLoading, isError: activeError } = useActiveLlmSettings();
    const updateActive = useUpdateActiveLlmSettings();
    const updateSecret = useUpdateProviderSecret();
    const deleteSecret = useDeleteProviderSecret();
    const testConnection = useTestActiveLlmSettings();

    const [expandedProvider, setExpandedProvider] = useState<string | null>(null);
    const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
    const [selectedModels, setSelectedModels] = useState<Record<string, string>>({});
    const [successMessage, setSuccessMessage] = useState("");

    const isLoading = catalogLoading || activeLoading;
    const isError = catalogError || activeError;

    const showSuccess = (message: string) => {
        setSuccessMessage(message);
        setTimeout(() => setSuccessMessage(""), 3000);
    };

    const handleSaveApiKey = async (providerId: string) => {
        const apiKey = apiKeys[providerId];
        if (!apiKey?.trim()) {
            return;
        }

        try {
            await updateSecret.mutateAsync({ providerId, apiKey });
            setApiKeys({ ...apiKeys, [providerId]: "" });
            setExpandedProvider(null);
            showSuccess("API Key 已保存");
        } catch (err) {
            console.error("Failed to save API key:", err);
        }
    };

    const handleDeleteApiKey = async (providerId: string) => {
        if (!confirm("确定要删除此提供方的 API Key 吗？")) {
            return;
        }

        try {
            await deleteSecret.mutateAsync(providerId);
            showSuccess("API Key 已删除");
        } catch (err) {
            console.error("Failed to delete API key:", err);
        }
    };

    const handleSelectProvider = async (provider: Provider) => {
        const modelId = selectedModels[provider.providerId] || provider.models[0]?.modelId;
        if (!modelId) {
            return;
        }

        try {
            await updateActive.mutateAsync({
                providerId: provider.providerId,
                modelId,
            });
            showSuccess("已设置为当前使用的提供方");
        } catch (err) {
            console.error("Failed to update active settings:", err);
        }
    };

    const handleTestConnection = async () => {
        try {
            const result = await testConnection.mutateAsync();
            if (result.ok) {
                showSuccess(`连接测试成功！延迟: ${result.latencyMs}ms`);
            }
        } catch (err: any) {
            console.error("Connection test failed:", err);
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="text-gray-500">加载设置中...</div>
            </div>
        );
    }

    if (isError) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="text-red-500">加载设置失败</div>
            </div>
        );
    }

    // Find active provider details
    const activeProvider = catalog?.providers.find((p) => p.providerId === activeSettings?.providerId);
    const activeModel = activeProvider?.models.find((m) => m.modelId === activeSettings?.modelId);

    return (
        <div className="space-y-8">
            {/* Success Message */}
            {successMessage && (
                <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
                    {successMessage}
                </div>
            )}

            {/* Active Settings Card */}
            {activeSettings && activeProvider ? (
                <div className="p-6 bg-blue-50 border-2 border-blue-200 rounded-lg">
                    <h3 className="text-lg font-semibold mb-4 text-blue-900">当前使用的配置</h3>
                    <div className="space-y-2 mb-4">
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-gray-600">提供方:</span>
                            <span className="font-medium">{activeProvider.displayName}</span>
                            {activeSettings.hasKey ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">
                                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                        <path
                                            fillRule="evenodd"
                                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                                            clipRule="evenodd"
                                        />
                                    </svg>
                                    已配置
                                </span>
                            ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full">
                                    ⚠️ 未配置 Key
                                </span>
                            )}
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-gray-600">模型:</span>
                            <span className="font-medium">{activeModel?.displayName || activeSettings.modelId}</span>
                        </div>
                    </div>
                    <div className="flex gap-3">
                        <button
                            onClick={handleTestConnection}
                            disabled={testConnection.isPending}
                            className="px-4 py-2 bg-blue-500 text-white text-sm rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                        >
                            {testConnection.isPending ? "测试中..." : "测试连接"}
                        </button>
                    </div>
                    {testConnection.isError && (
                        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                            连接测试失败: {testConnection.error?.message || "未知错误"}
                        </div>
                    )}
                </div>
            ) : (
                <div className="p-6 bg-gray-50 border-2 border-gray-200 border-dashed rounded-lg text-center">
                    <p className="text-gray-600">暂未配置模型提供方，请从下方列表中选择</p>
                </div>
            )}

            {/* Provider Catalog */}
            <div>
                <h3 className="text-lg font-semibold mb-4">可用的模型提供方</h3>
                <div className="space-y-4">
                    {catalog?.providers.map((provider) => {
                        const isExpanded = expandedProvider === provider.providerId;
                        const selectedModel = selectedModels[provider.providerId] || provider.models[0]?.modelId || "";

                        return (
                            <div
                                key={provider.providerId}
                                className={`p-5 rounded-lg transition-all ${provider.hasKey
                                        ? "bg-white border-2 border-green-200 shadow-sm"
                                        : "bg-gray-50 border-2 border-dashed border-gray-300"
                                    }`}
                            >
                                {/* Provider Header */}
                                <div className="flex items-start justify-between mb-3">
                                    <div className="flex items-center gap-3">
                                        {provider.hasKey ? (
                                            <div className="flex-shrink-0 w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
                                                <svg className="w-6 h-6 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                                                    <path
                                                        fillRule="evenodd"
                                                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                                                        clipRule="evenodd"
                                                    />
                                                </svg>
                                            </div>
                                        ) : (
                                            <div className="flex-shrink-0 w-10 h-10 bg-yellow-100 rounded-full flex items-center justify-center">
                                                <span className="text-xl">⚠️</span>
                                            </div>
                                        )}
                                        <div>
                                            <h4 className="text-base font-semibold">{provider.displayName}</h4>
                                            {provider.hasKey ? (
                                                <p className="text-xs text-green-600 mt-0.5">
                                                    API Key 已配置
                                                    {provider.secretUpdatedAtMs &&
                                                        ` · 更新于 ${new Date(provider.secretUpdatedAtMs).toLocaleDateString()}`}
                                                </p>
                                            ) : (
                                                <p className="text-xs text-yellow-600 mt-0.5">需要配置 API Key</p>
                                            )}
                                        </div>
                                    </div>
                                    <span
                                        className={`px-3 py-1 text-xs font-medium rounded-full ${provider.hasKey
                                                ? "bg-green-100 text-green-700"
                                                : "bg-yellow-100 text-yellow-700"
                                            }`}
                                    >
                                        {provider.hasKey ? "已配置" : "未配置"}
                                    </span>
                                </div>

                                {/* Model Selection */}
                                <div className="mb-3">
                                    <label className="block text-sm font-medium text-gray-700 mb-2">选择模型</label>
                                    <select
                                        value={selectedModel}
                                        onChange={(e) =>
                                            setSelectedModels({ ...selectedModels, [provider.providerId]: e.target.value })
                                        }
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                    >
                                        {provider.models.map((model) => (
                                            <option key={model.modelId} value={model.modelId}>
                                                {model.displayName}
                                            </option>
                                        ))}
                                    </select>
                                </div>

                                {/* API Key Management */}
                                <div className="mb-3">
                                    {isExpanded ? (
                                        <div className="space-y-2">
                                            <label className="block text-sm font-medium text-gray-700">API Key</label>
                                            <input
                                                type="password"
                                                value={apiKeys[provider.providerId] || ""}
                                                onChange={(e) =>
                                                    setApiKeys({ ...apiKeys, [provider.providerId]: e.target.value })
                                                }
                                                placeholder="输入 API Key"
                                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            />
                                            <div className="flex gap-2">
                                                <button
                                                    onClick={() => handleSaveApiKey(provider.providerId)}
                                                    disabled={updateSecret.isPending}
                                                    className="px-4 py-2 bg-green-500 text-white text-sm rounded-lg hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                                                >
                                                    {updateSecret.isPending ? "保存中..." : "保存"}
                                                </button>
                                                <button
                                                    onClick={() => setExpandedProvider(null)}
                                                    className="px-4 py-2 bg-gray-200 text-gray-700 text-sm rounded-lg hover:bg-gray-300 transition-colors"
                                                >
                                                    取消
                                                </button>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => setExpandedProvider(provider.providerId)}
                                                className="px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded-lg hover:bg-gray-200 transition-colors"
                                            >
                                                {provider.hasKey ? "更新 API Key" : "配置 API Key"}
                                            </button>
                                            {provider.hasKey && (
                                                <button
                                                    onClick={() => handleDeleteApiKey(provider.providerId)}
                                                    disabled={deleteSecret.isPending}
                                                    className="px-4 py-2 bg-red-100 text-red-700 text-sm rounded-lg hover:bg-red-200 disabled:bg-gray-200 disabled:cursor-not-allowed transition-colors"
                                                >
                                                    {deleteSecret.isPending ? "删除中..." : "删除 API Key"}
                                                </button>
                                            )}
                                        </div>
                                    )}
                                </div>

                                {/* Select Provider Button */}
                                <button
                                    onClick={() => handleSelectProvider(provider)}
                                    disabled={!provider.hasKey || updateActive.isPending}
                                    className="w-full px-4 py-2 bg-blue-500 text-white text-sm font-medium rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                                >
                                    {updateActive.isPending ? "设置中..." : "选择此提供方"}
                                </button>
                                {!provider.hasKey && (
                                    <p className="mt-2 text-xs text-gray-500 text-center">
                                        需要先配置 API Key 才能选择此提供方
                                    </p>
                                )}

                                {/* Error Messages */}
                                {updateSecret.isError && expandedProvider === provider.providerId && (
                                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                                        保存失败: {updateSecret.error?.message || "未知错误"}
                                    </div>
                                )}
                                {updateActive.isError && (
                                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                                        设置失败: {updateActive.error?.message || "未知错误"}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Info Note */}
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                    <strong>注意：</strong> API Key 仅用于配置，永不回显。修改后将立即生效。
                </p>
            </div>
        </div>
    );
}
