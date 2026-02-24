"use client";

import { useState } from "react";
import {
    useLlmCatalog,
    useActiveLlmSettings,
    useUpdateActiveLlmSettings,
    useUpdateProviderSecret,
    useDeleteProviderSecret,
    useTestActiveLlmSettings,
    useAddCustomModel,
    useDeleteCustomModel,
    useAddCustomProvider,
    useDeleteCustomProvider,
} from "@/lib/api/llmSettingsQueries";
import type { Provider } from "@/lib/contracts/llmSettingsTypes";

import { useTranslations } from "next-intl";

// ─── Sub-components ───────────────────────────────────────────────────────────

/** Badge shown next to custom models/providers */
function CustomBadge() {
    const t = useTranslations("Settings");
    return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-100 text-purple-700 leading-none">
            {t("customBadge")}
        </span>
    );
}

// ─── Add Custom Model Modal ───────────────────────────────────────────────────

interface AddCustomModelFormProps {
    providerId: string;
    onClose: () => void;
    onSuccess: (msg: string) => void;
}

function AddCustomModelForm({ providerId, onClose, onSuccess }: AddCustomModelFormProps) {
    const t = useTranslations("Settings");
    const [modelId, setModelId] = useState("");
    const [displayName, setDisplayName] = useState("");
    const addModel = useAddCustomModel();

    const handleSubmit = async () => {
        const mid = modelId.trim();
        if (!mid) return;
        try {
            await addModel.mutateAsync({
                providerId,
                request: { modelId: mid, displayName: displayName.trim() || mid },
            });
            onSuccess(t("addModelSuccess", { name: displayName.trim() || mid }));
            onClose();
        } catch (err) {
            console.error("Failed to add custom model:", err);
        }
    };

    return (
        <div className="mt-3 p-3 bg-purple-50 border border-purple-200 rounded-lg space-y-2">
            <p className="text-xs font-medium text-purple-800">{t("addCustomModelTitle")}</p>
            <input
                type="text"
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                placeholder={t("modelIdPlaceholder")}
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-purple-400"
            />
            <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder={t("displayNamePlaceholder")}
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-purple-400"
            />
            {addModel.isError && (
                <p className="text-xs text-red-600">
                    {t("addModelFailed", { error: (addModel.error as any)?.message || t("unknownError") })}
                </p>
            )}
            <div className="flex gap-2">
                <button
                    onClick={handleSubmit}
                    disabled={!modelId.trim() || addModel.isPending}
                    className="px-3 py-1.5 bg-purple-500 text-white text-xs rounded hover:bg-purple-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                    {addModel.isPending ? t("saving") : t("save")}
                </button>
                <button
                    onClick={onClose}
                    className="px-3 py-1.5 bg-gray-200 text-gray-700 text-xs rounded hover:bg-gray-300 transition-colors"
                >
                    {t("cancel")}
                </button>
            </div>
        </div>
    );
}

// ─── Add Custom Provider Form ─────────────────────────────────────────────────

interface AddCustomProviderFormProps {
    onClose: () => void;
    onSuccess: (msg: string) => void;
}

function AddCustomProviderForm({ onClose, onSuccess }: AddCustomProviderFormProps) {
    const t = useTranslations("Settings");
    const [form, setForm] = useState({
        providerId: "",
        displayName: "",
        baseUrl: "",
        modelId: "",
        modelDisplayName: "",
        apiKey: "",
    });
    const addProvider = useAddCustomProvider();
    const updateSecret = useUpdateProviderSecret();

    const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
        setForm((prev) => ({ ...prev, [field]: e.target.value }));

    const handleSubmit = async () => {
        const pid = form.providerId.trim();
        const dname = form.displayName.trim();
        const url = form.baseUrl.trim();
        const mid = form.modelId.trim();
        if (!pid || !dname || !url || !mid) return;

        try {
            await addProvider.mutateAsync({
                providerId: pid,
                displayName: dname,
                baseUrl: url,
                modelId: mid,
                modelDisplayName: form.modelDisplayName.trim() || mid,
            });

            // Optionally save API key
            if (form.apiKey.trim()) {
                await updateSecret.mutateAsync({ providerId: pid, apiKey: form.apiKey.trim() });
            }

            onSuccess(t("customProviderAdded", { name: dname }));
            onClose();
        } catch (err) {
            console.error("Failed to add custom provider:", err);
        }
    };

    const isSubmitting = addProvider.isPending || updateSecret.isPending;
    const submitError = addProvider.isError || updateSecret.isError;
    const submitErrorMsg = ((addProvider.error || updateSecret.error) as any)?.message || t("unknownError");

    const fields: { key: keyof typeof form; label: string; placeholder: string; required?: boolean; type?: string }[] = [
        { key: "providerId", label: "Provider ID", placeholder: t("providerIdPlaceholderCommon"), required: true },
        { key: "displayName", label: t("displayName"), placeholder: t("displayNamePlaceholder"), required: true },
        { key: "baseUrl", label: "Base URL", placeholder: "https://api.example.com/v1", required: true },
        { key: "modelId", label: t("firstModelId"), placeholder: "如 custom-model-v1", required: true },
        { key: "modelDisplayName", label: t("modelDisplayName"), placeholder: t("displayNamePlaceholder") },
        { key: "apiKey", label: "API Key", placeholder: t("apiKeyPlaceholder"), type: "password" },
    ];

    return (
        <div className="p-5 bg-purple-50 border-2 border-purple-200 rounded-lg space-y-3">
            <p className="font-semibold text-purple-900 text-sm">{t("addCustomProviderTitle")}</p>
            {fields.map((f) => (
                <div key={f.key}>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                        {f.label}
                        {f.required && <span className="text-red-500 ml-0.5">*</span>}
                    </label>
                    <input
                        type={f.type || "text"}
                        value={form[f.key]}
                        onChange={set(f.key)}
                        placeholder={f.placeholder}
                        className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-purple-400"
                    />
                </div>
            ))}

            {submitError && (
                <p className="text-xs text-red-600">{t("addModelFailed", { error: submitErrorMsg })}</p>
            )}

            <div className="flex gap-2 pt-1">
                <button
                    onClick={handleSubmit}
                    disabled={!form.providerId.trim() || !form.displayName.trim() || !form.baseUrl.trim() || !form.modelId.trim() || isSubmitting}
                    className="px-4 py-2 bg-purple-500 text-white text-sm rounded-lg hover:bg-purple-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                    {isSubmitting ? t("saving") : t("save")}
                </button>
                <button
                    onClick={onClose}
                    className="px-4 py-2 bg-gray-200 text-gray-700 text-sm rounded-lg hover:bg-gray-300 transition-colors"
                >
                    {t("cancel")}
                </button>
            </div>
        </div>
    );
}

// ─── Main SettingsForm ────────────────────────────────────────────────────────

export function SettingsForm() {
    const t = useTranslations("Settings");
    const { data: catalog, isLoading: catalogLoading, isError: catalogError } = useLlmCatalog();
    const { data: activeSettings, isLoading: activeLoading, isError: activeError } = useActiveLlmSettings();
    const updateActive = useUpdateActiveLlmSettings();
    const updateSecret = useUpdateProviderSecret();
    const deleteSecret = useDeleteProviderSecret();
    const testConnection = useTestActiveLlmSettings();
    const deleteCustomModel = useDeleteCustomModel();
    const deleteCustomProvider = useDeleteCustomProvider();

    const [expandedProvider, setExpandedProvider] = useState<string | null>(null);
    const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
    const [selectedModels, setSelectedModels] = useState<Record<string, string>>({});
    const [successMessage, setSuccessMessage] = useState("");
    // Track which provider has the "add custom model" form open
    const [addingModelFor, setAddingModelFor] = useState<string | null>(null);
    // Show/hide add custom provider form
    const [showAddProvider, setShowAddProvider] = useState(false);

    const isLoading = catalogLoading || activeLoading;
    const isError = catalogError || activeError;

    const showSuccess = (message: string) => {
        setSuccessMessage(message);
        setTimeout(() => setSuccessMessage(""), 3500);
    };

    const handleSaveApiKey = async (providerId: string) => {
        const apiKey = apiKeys[providerId];
        if (!apiKey?.trim()) return;
        try {
            await updateSecret.mutateAsync({ providerId, apiKey });
            setApiKeys({ ...apiKeys, [providerId]: "" });
            setExpandedProvider(null);
            showSuccess(t("apiKeySaved"));
        } catch (err) {
            console.error("Failed to save API key:", err);
        }
    };

    const handleDeleteApiKey = async (providerId: string) => {
        if (!confirm(t("deleteApiKeyConfirm"))) return;
        try {
            await deleteSecret.mutateAsync(providerId);
            showSuccess(t("apiKeyDeleted"));
        } catch (err) {
            console.error("Failed to delete API key:", err);
        }
    };

    const handleSelectProvider = async (provider: Provider) => {
        const modelId = selectedModels[provider.providerId] || provider.models[0]?.modelId;
        if (!modelId) return;
        try {
            await updateActive.mutateAsync({ providerId: provider.providerId, modelId });
            showSuccess(t("activeSetSuccess"));
        } catch (err) {
            console.error("Failed to update active settings:", err);
        }
    };

    const handleTestConnection = async () => {
        try {
            const result = await testConnection.mutateAsync();
            if (result.ok) {
                showSuccess(t("testSuccess", { latency: result.latencyMs ?? 0 }));
            }
        } catch (err: any) {
            console.error("Connection test failed:", err);
        }
    };

    const handleDeleteCustomModel = async (providerId: string, modelId: string) => {
        if (!confirm(t("deleteModelConfirm", { modelId }))) return;
        try {
            await deleteCustomModel.mutateAsync({ providerId, modelId });
            showSuccess(t("customModelDeleted"));
        } catch (err) {
            console.error("Failed to delete custom model:", err);
        }
    };

    const handleDeleteCustomProvider = async (providerId: string, displayName: string) => {
        if (!confirm(t("deleteProviderConfirm", { displayName }))) return;
        try {
            await deleteCustomProvider.mutateAsync(providerId);
            showSuccess(t("customProviderDeleted"));
        } catch (err) {
            console.error("Failed to delete custom provider:", err);
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="text-gray-500">{t("loading")}</div>
            </div>
        );
    }

    if (isError) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="text-red-500">{t("loadFailed")}</div>
            </div>
        );
    }

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
                    <h3 className="text-lg font-semibold mb-4 text-blue-900">{t("activeConfig")}</h3>
                    <div className="space-y-2 mb-4">
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-gray-600">{t("provider")}:</span>
                            <span className="font-medium">{activeProvider.displayName}</span>
                            {activeProvider.isCustom && <CustomBadge />}
                            {activeSettings.hasKey ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">
                                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                    </svg>
                                    {t("configured")}
                                </span>
                            ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full">
                                    {t("noApiKey")}
                                </span>
                            )}
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-gray-600">{t("model")}:</span>
                            <span className="font-medium">{activeModel?.displayName || activeSettings.modelId}</span>
                            {activeModel?.isCustom && <CustomBadge />}
                        </div>
                    </div>
                    <div className="flex gap-3">
                        <button
                            onClick={handleTestConnection}
                            disabled={testConnection.isPending}
                            className="px-4 py-2 bg-blue-500 text-white text-sm rounded-lg hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                        >
                            {testConnection.isPending ? t("testing") : t("testConnection")}
                        </button>
                    </div>
                    {testConnection.isError && (
                        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                            {t("testFailed", { error: (testConnection.error as any)?.message || t("unknownError") })}
                        </div>
                    )}
                </div>
            ) : (
                <div className="p-6 bg-gray-50 border-2 border-gray-200 border-dashed rounded-lg text-center">
                    <p className="text-gray-600">{t("noProviderConfigured")}</p>
                </div>
            )}

            {/* Provider Catalog */}
            <div>
                <h3 className="text-lg font-semibold mb-4">{t("availableProviders")}</h3>
                <div className="space-y-4">
                    {catalog?.providers.map((provider) => {
                        const isExpanded = expandedProvider === provider.providerId;
                        const isAddingModel = addingModelFor === provider.providerId;
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
                                                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                                </svg>
                                            </div>
                                        ) : (
                                            <div className="flex-shrink-0 w-10 h-10 bg-yellow-100 rounded-full flex items-center justify-center">
                                                <span className="text-xl">⚠️</span>
                                            </div>
                                        )}
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <h4 className="text-base font-semibold">{provider.displayName}</h4>
                                                {provider.isCustom && <CustomBadge />}
                                            </div>
                                            {provider.hasKey ? (
                                                <p className="text-xs text-green-600 mt-0.5">
                                                    {t("apiKeyConfigured")}
                                                    {provider.secretUpdatedAtMs &&
                                                        ` · ${t("updatedAt", { date: new Date(provider.secretUpdatedAtMs as number).toLocaleDateString() })}`}
                                                </p>
                                            ) : (
                                                <p className="text-xs text-yellow-600 mt-0.5">{t("needsApiKey")}</p>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span
                                            className={`px-3 py-1 text-xs font-medium rounded-full ${provider.hasKey
                                                ? "bg-green-100 text-green-700"
                                                : "bg-yellow-100 text-yellow-700"
                                                }`}
                                        >
                                            {provider.hasKey ? t("configured") : t("notConfigured")}
                                        </span>
                                        {/* Delete button for custom providers */}
                                        {provider.isCustom && (
                                            <button
                                                onClick={() => handleDeleteCustomProvider(provider.providerId, provider.displayName)}
                                                disabled={deleteCustomProvider.isPending}
                                                title={t("deleteProvider")}
                                                className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                                            >
                                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                </svg>
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {/* Model Selection */}
                                <div className="mb-3">
                                    <label className="block text-sm font-medium text-gray-700 mb-2">{t("selectModel")}</label>
                                    <div className="flex items-center gap-2">
                                        <select
                                            value={selectedModel}
                                            onChange={(e) =>
                                                setSelectedModels({ ...selectedModels, [provider.providerId]: e.target.value })
                                            }
                                            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                        >
                                            {provider.models.map((model) => (
                                                <option key={model.modelId} value={model.modelId}>
                                                    {model.displayName}
                                                    {model.isCustom ? t("customLabel") : ""}
                                                </option>
                                            ))}
                                        </select>

                                        {/* Delete custom model button — only shown when a custom model is selected */}
                                        {(() => {
                                            const sel = provider.models.find((m) => m.modelId === selectedModel);
                                            if (!sel?.isCustom) return null;
                                            return (
                                                <button
                                                    onClick={() => handleDeleteCustomModel(provider.providerId, selectedModel)}
                                                    disabled={deleteCustomModel.isPending}
                                                    title={t("deleteModel")}
                                                    className="p-2 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg border border-red-200 transition-colors"
                                                >
                                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                                    </svg>
                                                </button>
                                            );
                                        })()}
                                    </div>

                                    {/* Add custom model toggle */}
                                    {!isAddingModel ? (
                                        <button
                                            onClick={() => setAddingModelFor(provider.providerId)}
                                            className="mt-2 text-xs text-purple-600 hover:text-purple-800 hover:underline transition-colors"
                                        >
                                            {t("addCustomModel")}
                                        </button>
                                    ) : null}

                                    {isAddingModel && (
                                        <AddCustomModelForm
                                            providerId={provider.providerId}
                                            onClose={() => setAddingModelFor(null)}
                                            onSuccess={showSuccess}
                                        />
                                    )}
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
                                                placeholder={t("inputApiKey")}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                            />
                                            <div className="flex gap-2">
                                                <button
                                                    onClick={() => handleSaveApiKey(provider.providerId)}
                                                    disabled={updateSecret.isPending}
                                                    className="px-4 py-2 bg-green-500 text-white text-sm rounded-lg hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                                                >
                                                    {updateSecret.isPending ? t("saving") : t("save")}
                                                </button>
                                                <button
                                                    onClick={() => setExpandedProvider(null)}
                                                    className="px-4 py-2 bg-gray-200 text-gray-700 text-sm rounded-lg hover:bg-gray-300 transition-colors"
                                                >
                                                    {t("cancel")}
                                                </button>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => setExpandedProvider(provider.providerId)}
                                                className="px-4 py-2 bg-gray-100 text-gray-700 text-sm rounded-lg hover:bg-gray-200 transition-colors"
                                            >
                                                {provider.hasKey ? t("updateApiKey") : t("configApiKey")}
                                            </button>
                                            {provider.hasKey && (
                                                <button
                                                    onClick={() => handleDeleteApiKey(provider.providerId)}
                                                    disabled={deleteSecret.isPending}
                                                    className="px-4 py-2 bg-red-100 text-red-700 text-sm rounded-lg hover:bg-red-200 disabled:bg-gray-200 disabled:cursor-not-allowed transition-colors"
                                                >
                                                    {deleteSecret.isPending ? t("deletingApiKey") : t("deleteApiKey")}
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
                                    {updateActive.isPending ? t("selecting") : t("selectProvider")}
                                </button>
                                {!provider.hasKey && (
                                    <p className="mt-2 text-xs text-gray-500 text-center">
                                        {t("apiKeyRequiredToSelect")}
                                    </p>
                                )}

                                {/* Error Messages */}
                                {updateSecret.isError && expandedProvider === provider.providerId && (
                                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                                        {t("saveFailed", { error: (updateSecret.error as any)?.message || t("unknownError") })}
                                    </div>
                                )}
                                {updateActive.isError && (
                                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                                        {t("selectProviderFailed", { error: (updateActive.error as any)?.message || t("unknownError") })}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* Add Custom Provider */}
                <div className="mt-4">
                    {!showAddProvider ? (
                        <button
                            onClick={() => setShowAddProvider(true)}
                            className="w-full px-4 py-3 border-2 border-dashed border-purple-300 text-purple-600 text-sm font-medium rounded-lg hover:bg-purple-50 hover:border-purple-400 transition-colors"
                        >
                            {t("addCustomProvider")}
                        </button>
                    ) : (
                        <AddCustomProviderForm
                            onClose={() => setShowAddProvider(false)}
                            onSuccess={showSuccess}
                        />
                    )}
                </div>
            </div>

            {/* Info Note */}
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                    {t.rich("infoNote", { strong: (chunks) => <strong>{chunks}</strong> })}
                </p>
            </div>
        </div>
    );
}
