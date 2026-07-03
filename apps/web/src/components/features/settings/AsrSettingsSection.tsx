"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import {
    useActiveAsrSettings,
    useAddCustomAsrModel,
    useAsrCatalog,
    useDeleteAsrProviderSecret,
    useDeleteCustomAsrModel,
    useRemoteAsrModels,
    useTestAsrProviderSettings,
    useUpdateActiveAsrSettings,
    useUpdateAsrProviderSecret,
} from "@/lib/api/asrSettingsQueries";
import type { AsrCatalogModel, AsrRemoteModelsResponse } from "@/lib/contracts/asrSettingsTypes";

function mergeCatalogAndRemoteModels(
    catalogModels: AsrCatalogModel[],
    remote: AsrRemoteModelsResponse | undefined,
): AsrCatalogModel[] {
    const byId = new Map<string, AsrCatalogModel>();
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

interface AddCustomAsrModelFormProps {
    providerId: string;
    onClose: () => void;
    onSuccess: (name: string) => void;
}

function AddCustomAsrModelForm({ providerId, onClose, onSuccess }: AddCustomAsrModelFormProps) {
    const t = useTranslations("Settings");
    const [modelId, setModelId] = useState("");
    const [displayName, setDisplayName] = useState("");
    const addModel = useAddCustomAsrModel();

    const handleSubmit = async () => {
        const mid = modelId.trim();
        if (!mid) return;
        try {
            await addModel.mutateAsync({
                providerId,
                request: { modelId: mid, displayName: displayName.trim() || mid },
            });
            onSuccess(displayName.trim() || mid);
            onClose();
        } catch (err) {
            console.error("Failed to add custom ASR model:", err);
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
                    type="button"
                    onClick={handleSubmit}
                    disabled={!modelId.trim() || addModel.isPending}
                    className="px-4 py-2 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 disabled:bg-stone-300 disabled:cursor-not-allowed transition-colors"
                >
                    {addModel.isPending ? t("saving") : t("save")}
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

export function AsrSettingsSection() {
    const t = useTranslations("Settings.asr");
    const tRoot = useTranslations("Settings");
    const { data: catalog, isLoading: catalogLoading, isError: catalogError } = useAsrCatalog();
    const { data: activeData, isLoading: activeLoading } = useActiveAsrSettings();
    const updateActive = useUpdateActiveAsrSettings();
    const updateSecret = useUpdateAsrProviderSecret();
    const deleteSecret = useDeleteAsrProviderSecret();
    const testProvider = useTestAsrProviderSettings();
    const deleteCustomModel = useDeleteCustomAsrModel();

    const [selectedProviderId, setSelectedProviderId] = useState("dashscope");
    const [selectedModelId, setSelectedModelId] = useState("");
    const [cloudEnabled, setCloudEnabled] = useState(true);
    const [fallbackToLocal, setFallbackToLocal] = useState(true);
    const [apiKeyDraft, setApiKeyDraft] = useState("");
    const [isEditingKey, setIsEditingKey] = useState(false);
    const [isAddingModel, setIsAddingModel] = useState(false);

    useEffect(() => {
        if (!activeData?.configured) return;
        if (activeData.providerId) setSelectedProviderId(activeData.providerId);
        if (activeData.modelId) setSelectedModelId(activeData.modelId);
        setCloudEnabled(activeData.cloudEnabled);
        setFallbackToLocal(activeData.fallbackToLocal);
    }, [activeData]);

    const selectedProvider = useMemo(
        () => catalog?.providers.find((p) => p.providerId === selectedProviderId),
        [catalog, selectedProviderId],
    );

    const remote = useRemoteAsrModels(selectedProviderId, Boolean(selectedProvider?.hasKey));

    const mergedModels = useMemo(
        () => mergeCatalogAndRemoteModels(selectedProvider?.models || [], remote.data),
        [selectedProvider?.models, remote.data],
    );

    useEffect(() => {
        const ids = new Set(mergedModels.map((m) => m.modelId));
        if (ids.size === 0) {
            if (selectedModelId) setSelectedModelId("");
            return;
        }
        if (!selectedModelId || !ids.has(selectedModelId)) {
            setSelectedModelId(mergedModels[0]?.modelId ?? "");
        }
    }, [mergedModels, selectedModelId]);

    const handleProviderChange = (providerId: string) => {
        setSelectedProviderId(providerId);
        setIsEditingKey(false);
        setIsAddingModel(false);
        setApiKeyDraft("");
        setSelectedModelId("");
    };

    const handleSaveActive = async () => {
        if (!selectedModelId.trim()) {
            toast.error(tRoot("noModelsYet"));
            return;
        }
        try {
            await updateActive.mutateAsync({
                cloudEnabled,
                providerId: selectedProviderId,
                modelId: selectedModelId,
                fallbackToLocal,
            });
            toast.success(t("saved"));
        } catch (e) {
            toast.error(String(e));
        }
    };

    const handleSaveKey = async () => {
        if (!apiKeyDraft.trim()) return;
        try {
            await updateSecret.mutateAsync({ providerId: selectedProviderId, apiKey: apiKeyDraft.trim() });
            setApiKeyDraft("");
            setIsEditingKey(false);
            toast.success(tRoot("apiKeySaved"));
        } catch (e) {
            toast.error(String(e));
        }
    };

    const handleDeleteKey = async () => {
        try {
            await deleteSecret.mutateAsync(selectedProviderId);
            setIsEditingKey(false);
            setApiKeyDraft("");
            toast.success(tRoot("apiKeyDeleted"));
        } catch (e) {
            toast.error(String(e));
        }
    };

    const handleDeleteCustomModel = async (modelId: string) => {
        try {
            await deleteCustomModel.mutateAsync({ providerId: selectedProviderId, modelId });
            toast.success(tRoot("deleteModel", { modelId }));
        } catch (e) {
            toast.error(String(e));
        }
    };

    const handleTest = async () => {
        if (!selectedProvider?.hasKey || !selectedModelId.trim()) return;
        try {
            const result = await testProvider.mutateAsync({
                providerId: selectedProviderId,
                modelId: selectedModelId,
            });
            if (result.ok) {
                toast.success(t("testSuccess", { latency: result.latencyMs }));
            } else {
                const detail = result.message?.trim();
                toast.error(detail ? t("testFailedDetail", { detail }) : tRoot("testFailed", { error: tRoot("unknownError") }));
            }
        } catch (e) {
            toast.error(String(e));
        }
    };

    const remoteFailed = Boolean(selectedProvider?.hasKey && remote.data && !remote.data.ok);
    const remoteLoading = Boolean(selectedProvider?.hasKey && (remote.isLoading || remote.isFetching));
    const selectedModel = mergedModels.find((m) => m.modelId === selectedModelId);

    if (catalogLoading || activeLoading) {
        return <p className="text-sm text-stone-500">{tRoot("loading")}</p>;
    }

    if (catalogError || !catalog) {
        return <p className="text-sm text-red-600">{tRoot("loadFailed")}</p>;
    }

    return (
        <div className="space-y-6">
            <p className="text-sm text-stone-600">{t("desc")}</p>
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">{t("privacyNote")}</p>

            <div className="bg-white rounded-2xl border border-stone-200 shadow-sm p-6 space-y-4">
                <label className="flex items-center gap-3 text-sm font-medium text-stone-800">
                    <input
                        type="checkbox"
                        checked={cloudEnabled}
                        onChange={(e) => setCloudEnabled(e.target.checked)}
                        className="rounded border-stone-300"
                    />
                    {t("cloudEnabled")}
                </label>

                <div className="grid gap-4 sm:grid-cols-2">
                    <label className="block text-sm">
                        <span className="text-stone-500">{tRoot("provider")}</span>
                        <select
                            className="mt-1 w-full rounded-lg border border-stone-200 px-3 py-2"
                            value={selectedProviderId}
                            onChange={(e) => handleProviderChange(e.target.value)}
                        >
                            {catalog.providers.map((p) => (
                                <option key={p.providerId} value={p.providerId}>
                                    {p.displayName}
                                </option>
                            ))}
                        </select>
                    </label>
                </div>

                {selectedProvider?.notes ? (
                    <p className="text-xs text-stone-500 bg-stone-50 border border-stone-100 rounded-lg px-3 py-2">
                        {selectedProvider.notes}
                    </p>
                ) : null}

                <div className="border-t border-stone-100 pt-4 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium text-stone-700">{t("apiKey")}</span>
                        <span className="text-xs text-stone-500">
                            {selectedProvider?.hasKey ? tRoot("apiKeyConfigured") : tRoot("needsApiKey")}
                        </span>
                    </div>
                    {isEditingKey ? (
                        <div className="flex flex-wrap gap-2">
                            <input
                                type="password"
                                value={apiKeyDraft}
                                onChange={(e) => setApiKeyDraft(e.target.value)}
                                placeholder={tRoot("apiKeyPlaceholder")}
                                className="flex-1 min-w-[200px] rounded-lg border border-stone-200 px-3 py-2 text-sm"
                            />
                            <button
                                type="button"
                                onClick={handleSaveKey}
                                disabled={!apiKeyDraft.trim() || updateSecret.isPending}
                                className="px-3 py-2 rounded-lg bg-blue-600 text-white text-sm disabled:opacity-50"
                            >
                                {tRoot("save")}
                            </button>
                            <button
                                type="button"
                                onClick={() => {
                                    setIsEditingKey(false);
                                    setApiKeyDraft("");
                                }}
                                className="px-3 py-2 text-sm"
                            >
                                {tRoot("cancel")}
                            </button>
                        </div>
                    ) : (
                        <div className="flex flex-wrap gap-2">
                            <button
                                type="button"
                                onClick={() => {
                                    setIsEditingKey(true);
                                    setApiKeyDraft("");
                                }}
                                className="px-3 py-1.5 rounded-lg border border-stone-200 text-sm"
                            >
                                {selectedProvider?.hasKey ? tRoot("updateApiKey") : tRoot("configApiKey")}
                            </button>
                            {selectedProvider?.hasKey ? (
                                <button
                                    type="button"
                                    onClick={handleDeleteKey}
                                    disabled={deleteSecret.isPending}
                                    className="px-3 py-1.5 rounded-lg border border-red-200 text-red-700 text-sm disabled:opacity-50"
                                >
                                    {tRoot("deleteApiKey")}
                                </button>
                            ) : null}
                        </div>
                    )}
                </div>

                <div>
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                        <label className="block text-xs font-medium text-stone-600 uppercase tracking-wide">
                            {tRoot("selectModel")}
                        </label>
                        {selectedProvider?.hasKey && (
                            <button
                                type="button"
                                onClick={() => remote.refetch()}
                                disabled={remoteLoading}
                                className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50"
                            >
                                {remoteLoading ? tRoot("loadingRemoteModels") : tRoot("refreshRemoteModels")}
                            </button>
                        )}
                    </div>

                    {!selectedProvider?.hasKey ? (
                        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2">
                            {tRoot("configureApiKeyFirst")}
                        </p>
                    ) : (
                        <>
                            {remoteLoading && mergedModels.length === 0 && (
                                <p className="text-xs text-stone-500 mb-2">{tRoot("loadingRemoteModels")}</p>
                            )}
                            {remoteFailed && (
                                <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2 mb-2">
                                    {remote.data?.error?.message || tRoot("remoteModelsManualHint")}
                                </p>
                            )}
                            <div className="flex items-center gap-2">
                                <select
                                    className="flex-1 rounded-lg border border-stone-200 px-3 py-2 text-sm"
                                    value={selectedModelId}
                                    onChange={(e) => setSelectedModelId(e.target.value)}
                                    disabled={mergedModels.length === 0}
                                >
                                    {mergedModels.length === 0 ? (
                                        <option value="">{tRoot("noModelsYet")}</option>
                                    ) : (
                                        mergedModels.map((m) => (
                                            <option key={m.modelId} value={m.modelId}>
                                                {m.displayName}
                                                {m.isCustom ? tRoot("customLabel") : ""}
                                            </option>
                                        ))
                                    )}
                                </select>
                                {selectedModel?.isCustom ? (
                                    <button
                                        type="button"
                                        onClick={() => handleDeleteCustomModel(selectedModelId)}
                                        disabled={deleteCustomModel.isPending}
                                        title={tRoot("deleteModel")}
                                        className="p-2 text-stone-400 hover:text-red-500 hover:bg-red-50 rounded-xl border border-stone-200 transition-colors"
                                    >
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                    </button>
                                ) : null}
                            </div>
                        </>
                    )}

                    {!isAddingModel && selectedProvider?.hasKey && (
                        <button
                            type="button"
                            onClick={() => setIsAddingModel(true)}
                            className="mt-2 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 transition-colors"
                        >
                            {tRoot("addCustomModel")}
                        </button>
                    )}
                    {isAddingModel && (
                        <AddCustomAsrModelForm
                            providerId={selectedProviderId}
                            onClose={() => setIsAddingModel(false)}
                            onSuccess={(name) => toast.success(tRoot("addModelSuccess", { name }))}
                        />
                    )}
                </div>

                <label className="flex items-center gap-3 text-sm text-stone-700">
                    <input
                        type="checkbox"
                        checked={fallbackToLocal}
                        onChange={(e) => setFallbackToLocal(e.target.checked)}
                        className="rounded border-stone-300"
                    />
                    {t("fallbackToLocal")}
                </label>

                <div className="flex flex-wrap gap-3">
                    <button
                        type="button"
                        onClick={handleSaveActive}
                        disabled={updateActive.isPending || !selectedModelId.trim()}
                        className="px-4 py-2 rounded-lg bg-stone-900 text-white text-sm disabled:opacity-50"
                    >
                        {updateActive.isPending ? tRoot("saving") : t("saveActive")}
                    </button>
                    <button
                        type="button"
                        onClick={handleTest}
                        disabled={testProvider.isPending || !selectedProvider?.hasKey || !selectedModelId.trim()}
                        className="px-4 py-2 rounded-lg border border-stone-200 text-sm disabled:opacity-50"
                    >
                        {testProvider.isPending ? tRoot("testing") : tRoot("testConnection")}
                    </button>
                </div>
            </div>
        </div>
    );
}
