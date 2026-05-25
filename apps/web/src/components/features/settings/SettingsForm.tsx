"use client";

import { useEffect, useMemo, useState } from "react";
import {
    useLlmCatalog,
    useActiveLlmSettings,
    useUpdateActiveLlmSettings,
    useUpdateProviderSecret,
    useDeleteProviderSecret,
    useTestActiveLlmSettings,
    useTestProviderLlmSettings,
    useAddCustomModel,
    useDeleteCustomModel,
    useAddCustomProvider,
    useDeleteCustomProvider,
    useUpdateCustomProvider,
    useUpdateProviderProfile,
    useRemoteLlmModels,
} from "@/lib/api/llmSettingsQueries";
import type { ActiveSettingsResponse, Model, Provider, RemoteModelsResponse } from "@/lib/contracts/llmSettingsTypes";

import { useTranslations } from "next-intl";
import { toast } from "sonner";

function mergeCatalogAndRemoteModels(catalogModels: Model[], remote: RemoteModelsResponse | undefined): Model[] {
    const byId = new Map<string, Model>();
    if (remote?.ok) {
        for (const m of remote.models) {
            byId.set(m.modelId, { modelId: m.modelId, displayName: m.displayName, isCustom: false });
        }
    }
    for (const c of catalogModels) {
        if (!byId.has(c.modelId)) {
            byId.set(c.modelId, { ...c, isCustom: c.isCustom ?? false });
        }
    }
    return Array.from(byId.values());
}

// ─── Shared Design Tokens ─────────────────────────────────────────────────────

function CustomBadge() {
    const t = useTranslations("Settings");
    return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-semibold bg-blue-100 text-blue-700 leading-none tracking-wide">
            {t("customBadge")}
        </span>
    );
}

function StatusBadge({ configured }: { configured: boolean }) {
    const t = useTranslations("Settings");
    return configured ? (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                />
            </svg>
            {t("configured")}
        </span>
    ) : (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
            </svg>
            {t("notConfigured")}
        </span>
    );
}

function TestConnectionButton({
    onClick,
    disabled,
    isPending,
    className = "",
}: {
    onClick: () => void;
    disabled?: boolean;
    isPending?: boolean;
    className?: string;
}) {
    const t = useTranslations("Settings");
    return (
        <button
            type="button"
            onClick={onClick}
            disabled={disabled || isPending}
            className={`inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 disabled:bg-stone-300 disabled:cursor-not-allowed transition-colors shadow-sm ${className}`}
        >
            {isPending ? (
                <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    {t("testing")}
                </>
            ) : (
                <>
                    <svg className="w-4 h-4 xl:w-5 xl:h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    <span className="xl:text-base">{t("testConnection")}</span>
                </>
            )}
        </button>
    );
}

function ProviderIcon({ name, configured }: { name: string; configured: boolean }) {
    return (
        <div
            className={`flex-shrink-0 w-10 h-10 xl:w-12 xl:h-12 rounded-xl xl:rounded-2xl flex items-center justify-center font-bold text-base xl:text-lg ${
                configured ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"
            }`}
        >
            {name.charAt(0).toUpperCase()}
        </div>
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
        <div className="mt-3 p-4 bg-blue-50 border border-blue-200 rounded-xl space-y-3">
            <p className="text-xs font-semibold text-blue-800 uppercase tracking-wide">{t("addCustomModelTitle")}</p>
            <input
                type="text"
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                placeholder={t("modelIdPlaceholder")}
                className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
            />
            <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder={t("displayNamePlaceholder")}
                className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
            />
            {addModel.isError && (
                <p className="text-xs text-red-600">
                    {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                    {t("addModelFailed", { error: (addModel.error as any)?.message || t("unknownError") })}
                </p>
            )}
            <div className="flex gap-2">
                <button
                    onClick={handleSubmit}
                    disabled={!modelId.trim() || addModel.isPending}
                    className="px-4 py-2 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 disabled:bg-stone-300 disabled:cursor-not-allowed transition-colors"
                >
                    {addModel.isPending ? t("saving") : t("save")}
                </button>
                <button
                    onClick={onClose}
                    className="px-4 py-2 bg-stone-100 text-stone-600 text-xs font-medium rounded-lg hover:bg-stone-200 transition-colors"
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
        displayName: "",
        baseUrl: "",
        modelId: "",
        apiKey: "",
    });
    const addProvider = useAddCustomProvider();
    const updateSecret = useUpdateProviderSecret();

    const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
        setForm((prev) => ({ ...prev, [field]: e.target.value }));

    const handleSubmit = async () => {
        const dname = form.displayName.trim();
        const url = form.baseUrl.trim();
        const mid = form.modelId.trim();
        if (!dname || !url) return;

        const providerId = dname.toLowerCase();

        try {
            await addProvider.mutateAsync({
                displayName: dname,
                baseUrl: url,
                ...(mid ? { modelId: mid } : {}),
            });

            if (form.apiKey.trim()) {
                await updateSecret.mutateAsync({ providerId, apiKey: form.apiKey.trim() });
            }

            onSuccess(t("customProviderAdded", { name: dname }));
            onClose();
        } catch (err) {
            console.error("Failed to add custom provider:", err);
        }
    };

    const isSubmitting = addProvider.isPending || updateSecret.isPending;
    const submitError = addProvider.isError || updateSecret.isError;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const submitErrorMsg = ((addProvider.error || updateSecret.error) as any)?.message || t("unknownError");

    const fields: { key: keyof typeof form; label: string; placeholder: string; required?: boolean; type?: string }[] = [
        { key: "displayName", label: t("displayName"), placeholder: t("providerDisplayNamePlaceholder"), required: true },
        { key: "baseUrl", label: "Base URL", placeholder: "https://api.example.com/v1", required: true },
        { key: "modelId", label: t("firstModelId"), placeholder: t("firstModelIdOptionalPlaceholder") },
        { key: "apiKey", label: "API Key", placeholder: t("apiKeyPlaceholder"), type: "password" },
    ];

    return (
        <div className="mt-4 p-5 bg-blue-50 border border-blue-200 rounded-xl space-y-3">
            <p className="font-semibold text-blue-900 text-sm uppercase tracking-wide">{t("addCustomProviderTitle")}</p>
            <form autoComplete="off" onSubmit={(e) => e.preventDefault()} className="space-y-3">
            {fields.map((f) => (
                <div key={f.key}>
                    <label className="block text-xs font-medium text-stone-700 mb-1">
                        {f.label}
                        {f.required && <span className="text-red-500 ml-0.5">*</span>}
                    </label>
                    <input
                        type={f.type || "text"}
                        value={form[f.key]}
                        onChange={set(f.key)}
                        placeholder={f.placeholder}
                        autoComplete={f.type === "password" ? "new-password" : "off"}
                        name={`vh-custom-provider-${f.key}`}
                        className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                    />
                </div>
            ))}

            {submitError && <p className="text-xs text-red-600">{t("addModelFailed", { error: submitErrorMsg })}</p>}

            <div className="flex gap-2 pt-1">
                <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={
                        !form.displayName.trim() ||
                        !form.baseUrl.trim() ||
                        isSubmitting
                    }
                    className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:bg-stone-300 disabled:cursor-not-allowed transition-colors"
                >
                    {isSubmitting ? t("saving") : t("save")}
                </button>
                <button
                    type="button"
                    onClick={onClose}
                    className="px-4 py-2 bg-stone-100 text-stone-600 text-sm font-medium rounded-lg hover:bg-stone-200 transition-colors"
                >
                    {t("cancel")}
                </button>
            </div>
            </form>
        </div>
    );
}

// ─── Edit Provider Profile Form ───────────────────────────────────────────────

interface EditProviderProfileFormProps {
    provider: Provider;
    onClose: () => void;
    onSuccess: (msg: string) => void;
}

function EditProviderProfileForm({ provider, onClose, onSuccess }: EditProviderProfileFormProps) {
    const t = useTranslations("Settings");
    const [displayName, setDisplayName] = useState(provider.displayName);
    const [baseUrl, setBaseUrl] = useState(provider.baseUrl ?? "");
    const updateCustomProvider = useUpdateCustomProvider();
    const updateProviderProfile = useUpdateProviderProfile();

    const handleSubmit = async () => {
        const dname = displayName.trim();
        const url = baseUrl.trim();
        if (!dname || !url) return;

        try {
            if (provider.isCustom) {
                await updateCustomProvider.mutateAsync({
                    providerId: provider.providerId,
                    request: { displayName: dname, baseUrl: url },
                });
            } else {
                await updateProviderProfile.mutateAsync({
                    providerId: provider.providerId,
                    request: { displayName: dname, baseUrl: url },
                });
            }
            onSuccess(t("providerProfileUpdated", { name: dname }));
            onClose();
        } catch (err) {
            console.error("Failed to update provider profile:", err);
        }
    };

    const isPending = updateCustomProvider.isPending || updateProviderProfile.isPending;
    const isError = updateCustomProvider.isError || updateProviderProfile.isError;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const errorMsg = ((updateCustomProvider.error || updateProviderProfile.error) as any)?.message || t("unknownError");

    return (
        <div className="mt-4 p-4 bg-stone-50 border border-stone-200 rounded-xl space-y-3">
            <p className="text-xs font-semibold text-stone-700 uppercase tracking-wide">{t("editProviderTitle")}</p>
            <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">
                    {t("displayName")}
                    <span className="text-red-500 ml-0.5">*</span>
                </label>
                <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    autoComplete="off"
                    className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                />
            </div>
            <div>
                <label className="block text-xs font-medium text-stone-700 mb-1">
                    Base URL
                    <span className="text-red-500 ml-0.5">*</span>
                </label>
                <input
                    type="url"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="https://api.example.com/v1"
                    autoComplete="off"
                    className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                />
            </div>
            {isError && <p className="text-xs text-red-600">{t("addModelFailed", { error: errorMsg })}</p>}
            <div className="flex gap-2">
                <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={!displayName.trim() || !baseUrl.trim() || isPending}
                    className="px-4 py-2 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 disabled:bg-stone-300 disabled:cursor-not-allowed transition-colors"
                >
                    {isPending ? t("saving") : t("save")}
                </button>
                <button
                    type="button"
                    onClick={onClose}
                    className="px-4 py-2 bg-stone-100 text-stone-600 text-xs font-medium rounded-lg hover:bg-stone-200 transition-colors"
                >
                    {t("cancel")}
                </button>
            </div>
        </div>
    );
}

// ─── Per-provider card (uses remote model list query) ─────────────────────────

interface ProviderLlmCardProps {
    provider: Provider;
    llmActive: ActiveSettingsResponse;
    isCardOpen: boolean;
    onToggleCard: () => void;
    apiKeyEditProviderId: string | null;
    setApiKeyEditProviderId: (id: string | null) => void;
    apiKeys: Record<string, string>;
    setApiKeys: React.Dispatch<React.SetStateAction<Record<string, string>>>;
    selectedModels: Record<string, string>;
    setSelectedModels: React.Dispatch<React.SetStateAction<Record<string, string>>>;
    addingModelFor: string | null;
    setAddingModelFor: (id: string | null) => void;
    showSuccess: (msg: string) => void;
    handleSaveApiKey: (providerId: string) => Promise<void>;
    handleDeleteApiKey: (providerId: string) => Promise<void>;
    handleSelectProvider: (provider: Provider, modelId: string) => Promise<void>;
    handleTestProvider: (providerId: string, modelId: string) => Promise<void>;
    handleDeleteCustomModel: (providerId: string, modelId: string) => Promise<void>;
    handleDeleteCustomProvider: (providerId: string, displayName: string) => Promise<void>;
    testingProviderId: string | null;
    providerTestError: string | null;
    updateSecret: ReturnType<typeof useUpdateProviderSecret>;
    deleteSecret: ReturnType<typeof useDeleteProviderSecret>;
    updateActive: ReturnType<typeof useUpdateActiveLlmSettings>;
    deleteCustomModel: ReturnType<typeof useDeleteCustomModel>;
    deleteCustomProvider: ReturnType<typeof useDeleteCustomProvider>;
}

function ProviderLlmCard({
    provider,
    llmActive,
    isCardOpen,
    onToggleCard,
    apiKeyEditProviderId,
    setApiKeyEditProviderId,
    apiKeys,
    setApiKeys,
    selectedModels,
    setSelectedModels,
    addingModelFor,
    setAddingModelFor,
    showSuccess,
    handleSaveApiKey,
    handleDeleteApiKey,
    handleSelectProvider,
    handleTestProvider,
    handleDeleteCustomModel,
    handleDeleteCustomProvider,
    testingProviderId,
    providerTestError,
    updateSecret,
    deleteSecret,
    updateActive,
    deleteCustomModel,
    deleteCustomProvider,
}: ProviderLlmCardProps) {
    const t = useTranslations("Settings");
    const pid = provider.providerId;
    const remote = useRemoteLlmModels(pid, provider.hasKey);
    const [isEditingProvider, setIsEditingProvider] = useState(false);

    const mergedModels = useMemo(
        () => mergeCatalogAndRemoteModels(provider.models, remote.data),
        [provider.models, remote.data],
    );

    useEffect(() => {
        const ids = new Set(mergedModels.map((m) => m.modelId));
        setSelectedModels((s) => {
            const cur = (s[pid] || "").trim();
            if (ids.size === 0) {
                if (!cur) return s;
                return { ...s, [pid]: "" };
            }
            if (!cur || !ids.has(cur)) {
                const pick = mergedModels[0]?.modelId ?? "";
                if (pick === cur) return s;
                return { ...s, [pid]: pick };
            }
            return s;
        });
    }, [mergedModels, pid, setSelectedModels]);

    const isApiKeyEditing = apiKeyEditProviderId === pid;
    const isAddingModel = addingModelFor === pid;
    const isTesting = testingProviderId === pid;
    const selectedModel = selectedModels[pid] || "";
    const isCurrentActive =
        llmActive.configured &&
        llmActive.providerId === pid &&
        selectedModel === (llmActive.modelId || "");

    const remoteFailed = Boolean(provider.hasKey && remote.data && !remote.data.ok);
    const remoteLoading = provider.hasKey && (remote.isLoading || remote.isFetching);

    const openApiKeyEditor = () => {
        if (!isCardOpen) onToggleCard();
        setApiKeyEditProviderId(pid);
    };

    return (
        <div
            className={`bg-white rounded-2xl border transition-all duration-200 overflow-hidden ${
                isCurrentActive
                    ? "border-blue-200 shadow-md ring-1 ring-blue-200"
                    : "border-stone-200 shadow-sm hover:border-stone-300"
            }`}
        >
            {isCurrentActive && <div className="h-0.5 bg-gradient-to-r from-blue-500 to-blue-400" />}

            <button
                type="button"
                onClick={onToggleCard}
                aria-expanded={isCardOpen}
                className="w-full p-5 xl:p-6 flex items-center justify-between gap-3 text-left hover:bg-stone-50/80 transition-colors"
            >
                <div className="flex items-center gap-3 xl:gap-4 min-w-0">
                    <ProviderIcon name={provider.displayName} configured={provider.hasKey} />
                    <div className="min-w-0">
                        <div className="flex items-center gap-2 xl:gap-2.5 mb-1 flex-wrap">
                            <h4 className="text-base md:text-lg xl:text-xl font-semibold text-stone-900 leading-none truncate">
                                {provider.displayName}
                            </h4>
                            {provider.isCustom && <CustomBadge />}
                            {isCurrentActive && (
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-700">
                                    {t("selectedProvider")}
                                </span>
                            )}
                        </div>
                        {isCardOpen ? (
                            <>
                                {provider.baseUrl && (
                                    <p className="text-xs xl:text-sm text-stone-500 truncate mb-1">{provider.baseUrl}</p>
                                )}
                                {provider.hasKey ? (
                                    <p className="text-xs xl:text-sm text-emerald-600">
                                        {t("apiKeyConfigured")}
                                        {provider.secretUpdatedAtMs &&
                                            ` · ${t("updatedAt", { date: new Date(provider.secretUpdatedAtMs as number).toLocaleDateString() })}`}
                                    </p>
                                ) : (
                                    <p className="text-xs xl:text-sm text-amber-600">{t("needsApiKey")}</p>
                                )}
                            </>
                        ) : (
                            <p className="text-xs xl:text-sm text-stone-500 truncate">
                                {provider.baseUrl
                                    ? provider.baseUrl
                                    : provider.hasKey
                                      ? t("apiKeyConfigured")
                                      : t("needsApiKey")}
                            </p>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <StatusBadge configured={provider.hasKey} />
                    <button
                        type="button"
                        onClick={(e) => {
                            e.stopPropagation();
                            if (!isCardOpen) onToggleCard();
                            setIsEditingProvider(true);
                        }}
                        title={t("editProvider")}
                        className="p-1.5 xl:p-2 text-stone-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                    >
                        <svg className="w-4 h-4 xl:w-5 xl:h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                            />
                        </svg>
                    </button>
                    {provider.isCustom && (
                        <button
                            type="button"
                            onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteCustomProvider(provider.providerId, provider.displayName);
                            }}
                            disabled={deleteCustomProvider.isPending}
                            title={t("deleteProvider")}
                            className="p-1.5 xl:p-2 text-stone-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                        >
                            <svg className="w-4 h-4 xl:w-5 xl:h-5" fill="none" viewBox="0 0 24 24">
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                />
                            </svg>
                        </button>
                    )}
                    <svg
                        className={`w-5 h-5 text-stone-400 transition-transform duration-200 ${isCardOpen ? "rotate-180" : ""}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                </div>
            </button>

            {isCardOpen && (
            <div className="px-5 xl:px-6 pb-5 xl:pb-6 pt-0 border-t border-stone-100">
                {isEditingProvider && (
                    <EditProviderProfileForm
                        provider={provider}
                        onClose={() => setIsEditingProvider(false)}
                        onSuccess={(msg) => {
                            setIsEditingProvider(false);
                            showSuccess(msg);
                        }}
                    />
                )}
                {/* API Key first */}
                <div className="mb-4 xl:mb-6 mt-4 xl:mt-5">
                    <label className="block text-xs xl:text-sm font-medium text-stone-600 mb-1.5 uppercase tracking-wide">
                        API Key
                    </label>
                    {isApiKeyEditing ? (
                        <div className="p-4 bg-stone-50 rounded-xl border border-stone-200 space-y-3">
                            <input
                                type="password"
                                value={apiKeys[pid] || ""}
                                onChange={(e) => setApiKeys({ ...apiKeys, [pid]: e.target.value })}
                                placeholder={t("inputApiKey")}
                                className="w-full px-3 py-2 text-sm border border-stone-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
                            />
                            <div className="flex gap-2">
                                <button
                                    type="button"
                                    onClick={() => handleSaveApiKey(pid)}
                                    disabled={updateSecret.isPending}
                                    className="px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-xl hover:bg-emerald-700 disabled:bg-stone-300 disabled:cursor-not-allowed transition-colors"
                                >
                                    {updateSecret.isPending ? t("saving") : t("save")}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setApiKeyEditProviderId(null)}
                                    className="px-4 py-2 bg-stone-100 text-stone-600 text-sm font-medium rounded-xl hover:bg-stone-200 transition-colors"
                                >
                                    {t("cancel")}
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-wrap gap-2 xl:gap-3">
                            <button
                                type="button"
                                onClick={openApiKeyEditor}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 xl:px-4 xl:py-2.5 bg-stone-100 text-stone-700 text-sm xl:text-base font-medium rounded-xl hover:bg-stone-200 transition-colors"
                            >
                                <svg className="w-3.5 h-3.5 xl:w-5 xl:h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                                    />
                                </svg>
                                {provider.hasKey ? t("updateApiKey") : t("configApiKey")}
                            </button>
                            {provider.hasKey && (
                                <button
                                    type="button"
                                    onClick={() => handleDeleteApiKey(pid)}
                                    disabled={deleteSecret.isPending}
                                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-50 text-red-600 text-sm font-medium rounded-xl hover:bg-red-100 disabled:bg-stone-100 disabled:cursor-not-allowed transition-colors border border-red-100"
                                >
                                    {deleteSecret.isPending ? t("deletingApiKey") : t("deleteApiKey")}
                                </button>
                            )}
                        </div>
                    )}
                    {updateSecret.isError && isApiKeyEditing && (
                        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                            {t("saveFailed", { error: (updateSecret.error as any)?.message || t("unknownError") })}
                        </div>
                    )}
                </div>

                {/* Models */}
                <div className="mb-4 xl:mb-6">
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5 xl:mb-2">
                        <label className="block text-xs xl:text-sm font-medium text-stone-600 uppercase tracking-wide">
                            {t("selectModel")}
                        </label>
                        {provider.hasKey && (
                            <button
                                type="button"
                                onClick={() => remote.refetch()}
                                disabled={remoteLoading}
                                className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50"
                            >
                                {remoteLoading ? t("loadingRemoteModels") : t("refreshRemoteModels")}
                            </button>
                        )}
                    </div>

                    {!provider.hasKey ? (
                        <p className="text-xs xl:text-sm text-amber-700 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2">
                            {t("configureApiKeyFirst")}
                        </p>
                    ) : (
                        <>
                            {remoteLoading && mergedModels.length === 0 && (
                                <p className="text-xs text-stone-500 mb-2">{t("loadingRemoteModels")}</p>
                            )}
                            {remoteFailed && (
                                <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2 mb-2">
                                    {remote.data?.error?.message || t("remoteModelsManualHint")}
                                </p>
                            )}
                            <div className="flex items-center gap-2 xl:gap-3">
                                <select
                                    value={selectedModel}
                                    onChange={(e) => setSelectedModels({ ...selectedModels, [pid]: e.target.value })}
                                    disabled={!provider.hasKey || mergedModels.length === 0}
                                    className="flex-1 px-3 py-2 xl:px-4 xl:py-3 text-sm xl:text-base border border-stone-200 rounded-xl bg-stone-50 text-stone-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent focus:bg-white transition-colors disabled:opacity-60"
                                >
                                    {mergedModels.length === 0 ? (
                                        <option value="">{t("noModelsYet")}</option>
                                    ) : (
                                        mergedModels.map((model) => (
                                            <option key={model.modelId} value={model.modelId}>
                                                {model.displayName}
                                                {model.isCustom ? t("customLabel") : ""}
                                            </option>
                                        ))
                                    )}
                                </select>
                                {(() => {
                                    const sel = mergedModels.find((m) => m.modelId === selectedModel);
                                    if (!sel?.isCustom) return null;
                                    return (
                                        <button
                                            onClick={() => handleDeleteCustomModel(pid, selectedModel)}
                                            disabled={deleteCustomModel.isPending}
                                            title={t("deleteModel")}
                                            className="p-2 text-stone-400 hover:text-red-500 hover:bg-red-50 rounded-xl border border-stone-200 transition-colors"
                                        >
                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                            </svg>
                                        </button>
                                    );
                                })()}
                            </div>
                        </>
                    )}

                    {!isAddingModel && provider.hasKey && (
                        <button
                            onClick={() => setAddingModelFor(pid)}
                            className="mt-2 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 transition-colors"
                        >
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                            </svg>
                            {t("addCustomModel")}
                        </button>
                    )}
                    {isAddingModel && (
                        <AddCustomModelForm
                            providerId={pid}
                            onClose={() => setAddingModelFor(null)}
                            onSuccess={showSuccess}
                        />
                    )}
                </div>

                <div className="flex flex-col sm:flex-row gap-3">
                    {provider.hasKey && (
                        <TestConnectionButton
                            onClick={() => handleTestProvider(pid, selectedModel)}
                            disabled={!selectedModel}
                            isPending={isTesting}
                            className="sm:flex-1 justify-center"
                        />
                    )}
                    {isCurrentActive ? (
                        <button
                            type="button"
                            disabled
                            className="sm:flex-1 px-4 py-2.5 xl:px-5 xl:py-3.5 bg-emerald-500 text-white text-sm xl:text-base font-semibold rounded-xl cursor-not-allowed"
                        >
                            <span className="inline-flex items-center gap-2 xl:gap-3 justify-center w-full">
                                <svg className="w-4 h-4 xl:w-5 xl:h-5" fill="currentColor" viewBox="0 0 20 20">
                                    <path
                                        fillRule="evenodd"
                                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                                        clipRule="evenodd"
                                    />
                                </svg>
                                {t("selectedProvider")}
                            </span>
                        </button>
                    ) : (
                        <button
                            type="button"
                            onClick={() => handleSelectProvider(provider, selectedModel)}
                            disabled={!provider.hasKey || !selectedModel || updateActive.isPending}
                            className="sm:flex-1 px-4 py-2.5 xl:px-5 xl:py-3.5 bg-blue-600 text-white text-sm xl:text-base font-semibold rounded-xl hover:bg-blue-700 disabled:bg-stone-200 disabled:text-stone-400 disabled:cursor-not-allowed transition-colors shadow-sm"
                        >
                            {updateActive.isPending ? t("selecting") : t("selectProvider")}
                        </button>
                    )}
                </div>
                {!provider.hasKey && (
                    <p className="mt-2 xl:mt-3 text-xs xl:text-sm text-stone-400 text-center">{t("apiKeyRequiredToSelect")}</p>
                )}

                {providerTestError && (
                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                        {t("testFailed", { error: providerTestError })}
                    </div>
                )}

                {updateActive.isError && (
                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                        {t("selectProviderFailed", { error: (updateActive.error as any)?.message || t("unknownError") })}
                    </div>
                )}
            </div>
            )}
        </div>
    );
}

// ─── Main SettingsForm ────────────────────────────────────────────────────────

export function SettingsForm() {
    const t = useTranslations("Settings");
    const { data: catalog, isLoading: catalogLoading, isError: catalogError } = useLlmCatalog();
    const { data: llmActiveData, isLoading: activeLoading, isError: activeError } = useActiveLlmSettings();
    const updateActive = useUpdateActiveLlmSettings();
    const updateSecret = useUpdateProviderSecret();
    const deleteSecret = useDeleteProviderSecret();
    const testConnection = useTestActiveLlmSettings();
    const testProviderConnection = useTestProviderLlmSettings();
    const deleteCustomModel = useDeleteCustomModel();
    const deleteCustomProvider = useDeleteCustomProvider();

    const [openProviderIds, setOpenProviderIds] = useState<Set<string>>(() => new Set());
    const [apiKeyEditProviderId, setApiKeyEditProviderId] = useState<string | null>(null);
    const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
    const [selectedModels, setSelectedModels] = useState<Record<string, string>>({});
    const [addingModelFor, setAddingModelFor] = useState<string | null>(null);
    const [showAddProvider, setShowAddProvider] = useState(false);
    const [testingProviderId, setTestingProviderId] = useState<string | null>(null);
    const [providerTestErrors, setProviderTestErrors] = useState<Record<string, string>>({});

    const isLoading = catalogLoading || activeLoading;
    const isError = catalogError || activeError;

    const showSuccess = (message: string) => {
        toast.success(message);
    };

    useEffect(() => {
        if (!llmActiveData?.configured || !llmActiveData.providerId) return;
        setSelectedModels((prev) => ({
            ...prev,
            [llmActiveData.providerId as string]: llmActiveData.modelId || "",
        }));
    }, [llmActiveData?.configured, llmActiveData?.providerId, llmActiveData?.modelId]);

    const toggleProviderCard = (providerId: string) => {
        setOpenProviderIds((prev) => {
            const next = new Set(prev);
            if (next.has(providerId)) {
                next.delete(providerId);
                if (apiKeyEditProviderId === providerId) setApiKeyEditProviderId(null);
            } else {
                next.add(providerId);
            }
            return next;
        });
    };

    const handleSaveApiKey = async (providerId: string) => {
        const apiKey = apiKeys[providerId];
        if (!apiKey?.trim()) return;
        try {
            await updateSecret.mutateAsync({ providerId, apiKey });
            setApiKeys({ ...apiKeys, [providerId]: "" });
            setApiKeyEditProviderId(null);
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

    const handleSelectProvider = async (provider: Provider, modelId: string) => {
        const mid = modelId.trim();
        if (!mid) return;
        try {
            await updateActive.mutateAsync({ providerId: provider.providerId, modelId: mid });
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
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } catch (err: any) {
            console.error("Connection test failed:", err);
        }
    };

    const handleTestProvider = async (providerId: string, modelId: string) => {
        const mid = modelId.trim();
        if (!mid) return;
        setTestingProviderId(providerId);
        setProviderTestErrors((prev) => {
            const next = { ...prev };
            delete next[providerId];
            return next;
        });
        try {
            const result = await testProviderConnection.mutateAsync({ providerId, modelId: mid });
            if (result.ok) {
                showSuccess(t("testSuccess", { latency: result.latencyMs ?? 0 }));
            }
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } catch (err: any) {
            const message = err?.message || t("unknownError");
            setProviderTestErrors((prev) => ({ ...prev, [providerId]: message }));
            console.error("Provider connection test failed:", err);
        } finally {
            setTestingProviderId(null);
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
            <div className="flex items-center justify-center py-16">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-stone-200 border-t-blue-600 rounded-full animate-spin" />
                    <p className="text-sm text-stone-500">{t("loading")}</p>
                </div>
            </div>
        );
    }

    if (isError || !catalog) {
        return (
            <div className="flex items-center justify-center py-16">
                <div className="text-sm text-red-500 bg-red-50 border border-red-200 rounded-xl px-6 py-4">{t("loadFailed")}</div>
            </div>
        );
    }

    const llmActive: ActiveSettingsResponse = llmActiveData ?? {
        configured: false,
        providerId: null,
        modelId: null,
        hasKey: false,
        updatedAtMs: null,
    };

    const activeProvider =
        llmActive.configured && llmActive.providerId
            ? catalog.providers.find((p) => p.providerId === llmActive.providerId)
            : undefined;
    const activeModel = activeProvider?.models.find((m) => m.modelId === llmActive.modelId);

    return (
        <div className="space-y-8">
            {llmActive.configured && llmActive.providerId ? (
                <div className="bg-white rounded-2xl border border-stone-200 shadow-sm overflow-hidden">
                    <div className="h-1 bg-gradient-to-r from-blue-500 to-blue-400" />
                    <div className="p-6 xl:p-8">
                        <h3 className="text-sm xl:text-lg font-semibold text-stone-500 uppercase tracking-wider mb-4 xl:mb-5">{t("activeConfig")}</h3>
                        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 xl:gap-x-8 xl:gap-y-4 mb-5 xl:mb-6">
                            <div className="flex items-center gap-2 xl:gap-3">
                                <span className="text-xs xl:text-sm text-stone-400 uppercase tracking-wide">{t("provider")}</span>
                                <span className="font-semibold text-stone-900 xl:text-xl">
                                    {activeProvider?.displayName || llmActive.providerId}
                                </span>
                                {activeProvider?.isCustom && <CustomBadge />}
                                {llmActive.hasKey ? (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 xl:px-3 xl:py-1 bg-emerald-50 text-emerald-700 text-xs xl:text-sm rounded-full border border-emerald-200">
                                        <svg className="w-3 h-3 xl:w-4 xl:h-4" fill="currentColor" viewBox="0 0 20 20">
                                            <path
                                                fillRule="evenodd"
                                                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                                                clipRule="evenodd"
                                            />
                                        </svg>
                                        {t("configured")}
                                    </span>
                                ) : (
                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 xl:px-3 xl:py-1 bg-amber-50 text-amber-700 text-xs xl:text-sm rounded-full border border-amber-200">
                                        {t("noApiKey")}
                                    </span>
                                )}
                            </div>
                            <div className="w-px h-4 xl:h-6 bg-stone-200 hidden sm:block" />
                            <div className="flex items-center gap-2 xl:gap-3">
                                <span className="text-xs xl:text-sm text-stone-400 uppercase tracking-wide">{t("model")}</span>
                                <span className="font-semibold text-stone-900 xl:text-xl">
                                    {activeModel?.displayName || llmActive.modelId}
                                </span>
                                {activeModel?.isCustom && <CustomBadge />}
                            </div>
                        </div>
                        <div className="flex gap-3">
                            <TestConnectionButton
                                onClick={handleTestConnection}
                                disabled={!llmActive.hasKey}
                                isPending={testConnection.isPending}
                            />
                        </div>
                        {testConnection.isError && (
                            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                {t("testFailed", { error: (testConnection.error as any)?.message || t("unknownError") })}
                            </div>
                        )}
                    </div>
                </div>
            ) : (
                <div className="p-8 bg-stone-50 border-2 border-dashed border-stone-200 rounded-2xl text-center">
                    <svg className="w-10 h-10 text-stone-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z"
                        />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <p className="text-stone-500 text-sm">{t("noProviderConfigured")}</p>
                </div>
            )}

            <div>
                <h3 className="text-sm xl:text-lg font-semibold text-stone-500 uppercase tracking-wider mb-4 xl:mb-5">{t("availableProviders")}</h3>
                <div className="space-y-2 xl:space-y-2.5">
                    {catalog?.providers.map((provider) => (
                        <ProviderLlmCard
                            key={provider.providerId}
                            provider={provider}
                            llmActive={llmActive}
                            isCardOpen={openProviderIds.has(provider.providerId)}
                            onToggleCard={() => toggleProviderCard(provider.providerId)}
                            apiKeyEditProviderId={apiKeyEditProviderId}
                            setApiKeyEditProviderId={setApiKeyEditProviderId}
                            apiKeys={apiKeys}
                            setApiKeys={setApiKeys}
                            selectedModels={selectedModels}
                            setSelectedModels={setSelectedModels}
                            addingModelFor={addingModelFor}
                            setAddingModelFor={setAddingModelFor}
                            showSuccess={showSuccess}
                            handleSaveApiKey={handleSaveApiKey}
                            handleDeleteApiKey={handleDeleteApiKey}
                            handleSelectProvider={handleSelectProvider}
                            handleTestProvider={handleTestProvider}
                            handleDeleteCustomModel={handleDeleteCustomModel}
                            handleDeleteCustomProvider={handleDeleteCustomProvider}
                            testingProviderId={testingProviderId}
                            providerTestError={providerTestErrors[provider.providerId] ?? null}
                            updateSecret={updateSecret}
                            deleteSecret={deleteSecret}
                            updateActive={updateActive}
                            deleteCustomModel={deleteCustomModel}
                            deleteCustomProvider={deleteCustomProvider}
                        />
                    ))}
                </div>

                <div className="mt-4">
                    {!showAddProvider ? (
                        <button
                            onClick={() => setShowAddProvider(true)}
                            className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-blue-200 text-blue-600 text-sm font-medium rounded-2xl hover:bg-blue-50 hover:border-blue-300 transition-colors"
                        >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                            </svg>
                            {t("addCustomProvider")}
                        </button>
                    ) : (
                        <AddCustomProviderForm onClose={() => setShowAddProvider(false)} onSuccess={showSuccess} />
                    )}
                </div>
            </div>

            <div className="p-4 bg-stone-100 border border-stone-200 rounded-2xl flex gap-3">
                <svg className="w-4 h-4 mt-0.5 shrink-0 text-stone-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-sm text-stone-600 leading-relaxed">
                    {t.rich("infoNote", { strong: (chunks) => <strong className="text-stone-800">{chunks}</strong> })}
                </p>
            </div>
        </div>
    );
}
