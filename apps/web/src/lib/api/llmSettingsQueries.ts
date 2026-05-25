import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";
import {
    fetchLlmCatalog,
    fetchActiveLlmSettings,
    updateActiveLlmSettings,
    updateProviderSecret,
    deleteProviderSecret,
    testActiveLlmSettings,
    testProviderLlmSettings,
    fetchRemoteLlmModels,
    addCustomModel,
    deleteCustomModel,
    addCustomProvider,
    deleteCustomProvider,
} from "./llmSettingsApi";
import type {
    UpdateActiveRequest,
    AddCustomModelRequest,
    AddCustomProviderRequest,
} from "../contracts/llmSettingsTypes";

// Query hook for LLM catalog
export function useLlmCatalog() {
    return useQuery({
        queryKey: queryKeys.llmCatalog,
        queryFn: fetchLlmCatalog,
    });
}

// Query hook for active LLM settings
export function useActiveLlmSettings() {
    return useQuery({
        queryKey: queryKeys.llmActive,
        queryFn: fetchActiveLlmSettings,
    });
}

export function useRemoteLlmModels(providerId: string, enabled: boolean) {
    return useQuery({
        queryKey: queryKeys.llmRemoteModels(providerId),
        queryFn: () => fetchRemoteLlmModels(providerId),
        enabled: Boolean(providerId) && enabled,
    });
}

// Mutation hook for updating active LLM settings
export function useUpdateActiveLlmSettings() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (request: UpdateActiveRequest) => updateActiveLlmSettings(request),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queryKeys.llmActive });
            queryClient.invalidateQueries({ queryKey: queryKeys.llmCatalog });
        },
    });
}

// Mutation hook for updating provider secret
export function useUpdateProviderSecret() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ providerId, apiKey }: { providerId: string; apiKey: string }) =>
            updateProviderSecret(providerId, apiKey),
        onSuccess: (_data, { providerId }) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.llmCatalog });
            queryClient.invalidateQueries({ queryKey: queryKeys.llmRemoteModels(providerId) });
        },
    });
}

// Mutation hook for deleting provider secret
export function useDeleteProviderSecret() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (providerId: string) => deleteProviderSecret(providerId),
        onSuccess: (_data, providerId) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.llmCatalog });
            queryClient.invalidateQueries({ queryKey: queryKeys.llmRemoteModels(providerId) });
        },
    });
}

// Mutation hook for testing active LLM settings
export function useTestActiveLlmSettings() {
    return useMutation({
        mutationFn: testActiveLlmSettings,
    });
}

export function useTestProviderLlmSettings() {
    return useMutation({
        mutationFn: ({ providerId, modelId }: { providerId: string; modelId: string }) =>
            testProviderLlmSettings(providerId, modelId),
    });
}

// ─── Custom models ────────────────────────────────────────────────────────────

export function useAddCustomModel() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ providerId, request }: { providerId: string; request: AddCustomModelRequest }) =>
            addCustomModel(providerId, request),
        onSuccess: (_data, { providerId }) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.llmCatalog });
            queryClient.invalidateQueries({ queryKey: queryKeys.llmRemoteModels(providerId) });
        },
    });
}

export function useDeleteCustomModel() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ providerId, modelId }: { providerId: string; modelId: string }) =>
            deleteCustomModel(providerId, modelId),
        onSuccess: (_data, { providerId }) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.llmCatalog });
            queryClient.invalidateQueries({ queryKey: queryKeys.llmRemoteModels(providerId) });
        },
    });
}

// ─── Custom providers ─────────────────────────────────────────────────────────

export function useAddCustomProvider() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (request: AddCustomProviderRequest) => addCustomProvider(request),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queryKeys.llmCatalog });
        },
    });
}

export function useDeleteCustomProvider() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (providerId: string) => deleteCustomProvider(providerId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queryKeys.llmCatalog });
            queryClient.invalidateQueries({ queryKey: queryKeys.llmActive });
        },
    });
}
