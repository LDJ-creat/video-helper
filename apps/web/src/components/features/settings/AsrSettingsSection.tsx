"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import {
    useActiveAsrSettings,
    useAsrCatalog,
    useDeleteAsrProviderSecret,
    useTestAsrProviderSettings,
    useUpdateActiveAsrSettings,
    useUpdateAsrProviderSecret,
} from "@/lib/api/asrSettingsQueries";

export function AsrSettingsSection() {
    const t = useTranslations("Settings.asr");
    const tRoot = useTranslations("Settings");
    const { data: catalog, isLoading: catalogLoading, isError: catalogError } = useAsrCatalog();
    const { data: activeData, isLoading: activeLoading } = useActiveAsrSettings();
    const updateActive = useUpdateActiveAsrSettings();
    const updateSecret = useUpdateAsrProviderSecret();
    const deleteSecret = useDeleteAsrProviderSecret();
    const testProvider = useTestAsrProviderSettings();

    const [selectedProviderId, setSelectedProviderId] = useState("dashscope");
    const [selectedModelId, setSelectedModelId] = useState("paraformer-v2");
    const [cloudEnabled, setCloudEnabled] = useState(true);
    const [languageHints, setLanguageHints] = useState("zh,en");
    const [fallbackToLocal, setFallbackToLocal] = useState(true);
    const [apiKeyDraft, setApiKeyDraft] = useState("");
    const [isEditingKey, setIsEditingKey] = useState(false);

    useEffect(() => {
        if (!activeData?.configured) return;
        if (activeData.providerId) setSelectedProviderId(activeData.providerId);
        if (activeData.modelId) setSelectedModelId(activeData.modelId);
        setCloudEnabled(activeData.cloudEnabled);
        setLanguageHints((activeData.languageHints || ["zh", "en"]).join(","));
        setFallbackToLocal(activeData.fallbackToLocal);
    }, [activeData]);

    const selectedProvider = useMemo(
        () => catalog?.providers.find((p) => p.providerId === selectedProviderId),
        [catalog, selectedProviderId],
    );

    const handleProviderChange = (providerId: string) => {
        setSelectedProviderId(providerId);
        setIsEditingKey(false);
        setApiKeyDraft("");
        const provider = catalog?.providers.find((p) => p.providerId === providerId);
        if (provider?.models[0]) setSelectedModelId(provider.models[0].modelId);
    };

    const handleSaveActive = async () => {
        try {
            await updateActive.mutateAsync({
                cloudEnabled,
                providerId: selectedProviderId,
                modelId: selectedModelId,
                languageHints: languageHints.split(",").map((s) => s.trim()).filter(Boolean),
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

    const handleTest = async () => {
        if (!selectedProvider?.hasKey) return;
        try {
            const result = await testProvider.mutateAsync({
                providerId: selectedProviderId,
                modelId: selectedModelId,
                languageHints: languageHints.split(",").map((s) => s.trim()).filter(Boolean),
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
                    <label className="block text-sm">
                        <span className="text-stone-500">{tRoot("model")}</span>
                        <select
                            className="mt-1 w-full rounded-lg border border-stone-200 px-3 py-2"
                            value={selectedModelId}
                            onChange={(e) => setSelectedModelId(e.target.value)}
                        >
                            {(selectedProvider?.models || []).map((m) => (
                                <option key={m.modelId} value={m.modelId}>
                                    {m.displayName}
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

                <label className="block text-sm">
                    <span className="text-stone-500">{t("languageHints")}</span>
                    <input
                        className="mt-1 w-full rounded-lg border border-stone-200 px-3 py-2 font-mono text-sm"
                        value={languageHints}
                        onChange={(e) => setLanguageHints(e.target.value)}
                        placeholder="zh,en"
                    />
                </label>

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
                        disabled={updateActive.isPending}
                        className="px-4 py-2 rounded-lg bg-stone-900 text-white text-sm disabled:opacity-50"
                    >
                        {updateActive.isPending ? tRoot("saving") : t("saveActive")}
                    </button>
                    <button
                        type="button"
                        onClick={handleTest}
                        disabled={testProvider.isPending || !selectedProvider?.hasKey}
                        className="px-4 py-2 rounded-lg border border-stone-200 text-sm disabled:opacity-50"
                    >
                        {testProvider.isPending ? tRoot("testing") : tRoot("testConnection")}
                    </button>
                </div>
            </div>
        </div>
    );
}
