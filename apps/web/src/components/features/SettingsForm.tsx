"use client";

import { useState, useEffect } from "react";
import { useSettings, useUpdateSettings } from "@/lib/api/settingsQueries";
import type { AnalyzeProvider, UpdateSettingsRequest } from "@/lib/contracts/settingsTypes";

const PROVIDER_OPTIONS: { value: AnalyzeProvider; label: string }[] = [
    { value: "llm", label: "LLM (大语言模型)" },
    { value: "rules", label: "Rules (规则引擎)" },
];

export function SettingsForm() {
    const { data: settings, isLoading, isError, error } = useSettings();
    const updateSettings = useUpdateSettings();

    const [formData, setFormData] = useState<UpdateSettingsRequest>({
        provider: "llm",
        baseUrl: null,
        model: null,
        timeoutS: 60,
        allowRulesFallback: true,
        debug: false,
    });

    const [successMessage, setSuccessMessage] = useState("");

    // Update form data when settings are loaded
    useEffect(() => {
        if (settings) {
            setFormData({
                provider: settings.provider,
                baseUrl: settings.baseUrl,
                model: settings.model,
                timeoutS: settings.timeoutS,
                allowRulesFallback: settings.allowRulesFallback,
                debug: settings.debug,
            });
        }
    }, [settings]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSuccessMessage("");

        try {
            await updateSettings.mutateAsync(formData);
            setSuccessMessage("设置已保存并立即生效");
            setTimeout(() => setSuccessMessage(""), 3000);
        } catch (err) {
            // Error will be handled by the mutation error state
            console.error("Failed to save settings:", err);
        }
    };

    const handleReset = () => {
        if (settings) {
            setFormData({
                provider: settings.provider,
                baseUrl: settings.baseUrl,
                model: settings.model,
                timeoutS: settings.timeoutS,
                allowRulesFallback: settings.allowRulesFallback,
                debug: settings.debug,
            });
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
                <div className="text-red-500">
                    加载设置失败: {error?.message || "未知错误"}
                </div>
            </div>
        );
    }

    return (
        <form onSubmit={handleSubmit} className="max-w-2xl space-y-6">
            {/* Provider 选择 */}
            <div>
                <label htmlFor="provider" className="block text-sm font-medium text-gray-700 mb-2">
                    Provider
                </label>
                <select
                    id="provider"
                    value={formData.provider}
                    onChange={(e) => setFormData({ ...formData, provider: e.target.value as AnalyzeProvider })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    required
                >
                    {PROVIDER_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                            {option.label}
                        </option>
                    ))}
                </select>
            </div>

            {/* Base URL */}
            <div>
                <label htmlFor="baseUrl" className="block text-sm font-medium text-gray-700 mb-2">
                    Base URL <span className="text-gray-500 text-xs">(可选)</span>
                </label>
                <input
                    type="url"
                    id="baseUrl"
                    value={formData.baseUrl || ""}
                    onChange={(e) => setFormData({ ...formData, baseUrl: e.target.value || null })}
                    placeholder="https://integrate.api.nvidia.com/v1"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="mt-1 text-xs text-gray-500">
                    LLM provider base URL（不含 key）
                </p>
            </div>

            {/* Model */}
            <div>
                <label htmlFor="model" className="block text-sm font-medium text-gray-700 mb-2">
                    Model <span className="text-gray-500 text-xs">(可选)</span>
                </label>
                <input
                    type="text"
                    id="model"
                    value={formData.model || ""}
                    onChange={(e) => setFormData({ ...formData, model: e.target.value || null })}
                    placeholder="minimax-2.1"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
            </div>

            {/* Timeout */}
            <div>
                <label htmlFor="timeoutS" className="block text-sm font-medium text-gray-700 mb-2">
                    Timeout (秒)
                </label>
                <input
                    type="number"
                    id="timeoutS"
                    value={formData.timeoutS || 60}
                    onChange={(e) => setFormData({ ...formData, timeoutS: parseInt(e.target.value) || 60 })}
                    min="1"
                    max="600"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
            </div>

            {/* Allow Rules Fallback */}
            <div className="flex items-center gap-3">
                <input
                    type="checkbox"
                    id="allowRulesFallback"
                    checked={formData.allowRulesFallback ?? true}
                    onChange={(e) => setFormData({ ...formData, allowRulesFallback: e.target.checked })}
                    className="w-4 h-4 text-blue-500 border-gray-300 rounded focus:ring-blue-500"
                />
                <label htmlFor="allowRulesFallback" className="text-sm font-medium text-gray-700">
                    允许 Rules Fallback（当 LLM 不可用时降级到规则引擎）
                </label>
            </div>

            {/* Debug */}
            <div className="flex items-center gap-3">
                <input
                    type="checkbox"
                    id="debug"
                    checked={formData.debug ?? false}
                    onChange={(e) => setFormData({ ...formData, debug: e.target.checked })}
                    className="w-4 h-4 text-blue-500 border-gray-300 rounded focus:ring-blue-500"
                />
                <label htmlFor="debug" className="text-sm font-medium text-gray-700">
                    Debug 模式（输出安全元数据）
                </label>
            </div>

            {/* Success Message */}
            {successMessage && (
                <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
                    {successMessage}
                </div>
            )}

            {/* Error Message */}
            {updateSettings.isError && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                    保存失败: {updateSettings.error?.message || "未知错误"}
                </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-4">
                <button
                    type="submit"
                    disabled={updateSettings.isPending}
                    className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                    {updateSettings.isPending ? "保存中..." : "保存设置"}
                </button>

                <button
                    type="button"
                    onClick={handleReset}
                    disabled={updateSettings.isPending}
                    className="px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors"
                >
                    重置
                </button>
            </div>

            {/* Info Note */}
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                    <strong>注意：</strong> API Key 永不返回/落盘。Key 只允许从环境变量（LLM_API_KEY）或请求头（X-LLM-API-KEY）注入。
                </p>
            </div>
        </form>
    );
}
