import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";
import {
    fetchLlmCatalog,
    fetchActiveLlmSettings,
    updateActiveLlmSettings,
    updateProviderSecret,
    deleteProviderSecret,
    testActiveLlmSettings,
} from "./llmSettingsApi";
import type { UpdateActiveRequest } from "../contracts/llmSettingsTypes";

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

// Mutation hook for updating active LLM settings
export function useUpdateActiveLlmSettings() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (request: UpdateActiveRequest) => updateActiveLlmSettings(request),
        onSuccess: () => {
            // Invalidate both active settings and catalog (hasKey status may change)
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
        onSuccess: () => {
            // Invalidate catalog to refresh hasKey status
            queryClient.invalidateQueries({ queryKey: queryKeys.llmCatalog });
        },
    });
}

// Mutation hook for deleting provider secret
export function useDeleteProviderSecret() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (providerId: string) => deleteProviderSecret(providerId),
        onSuccess: () => {
            // Invalidate catalog to refresh hasKey status
            queryClient.invalidateQueries({ queryKey: queryKeys.llmCatalog });
        },
    });
}

// Mutation hook for testing active LLM settings
export function useTestActiveLlmSettings() {
    return useMutation({
        mutationFn: testActiveLlmSettings,
    });
}
