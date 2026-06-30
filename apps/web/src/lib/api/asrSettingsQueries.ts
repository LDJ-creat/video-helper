import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";
import {
    deleteAsrProviderSecret,
    fetchActiveAsrSettings,
    fetchAsrCatalog,
    testActiveAsrSettings,
    testAsrProviderSettings,
    updateActiveAsrSettings,
    updateAsrProviderSecret,
} from "./asrSettingsApi";
import type { UpdateAsrActiveRequest } from "../contracts/asrSettingsTypes";

export function useAsrCatalog() {
    return useQuery({
        queryKey: queryKeys.asrCatalog,
        queryFn: fetchAsrCatalog,
    });
}

export function useActiveAsrSettings() {
    return useQuery({
        queryKey: queryKeys.asrActive,
        queryFn: fetchActiveAsrSettings,
    });
}

export function useUpdateActiveAsrSettings() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (request: UpdateAsrActiveRequest) => updateActiveAsrSettings(request),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queryKeys.asrActive });
            queryClient.invalidateQueries({ queryKey: queryKeys.asrCatalog });
        },
    });
}

export function useUpdateAsrProviderSecret() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ providerId, apiKey }: { providerId: string; apiKey: string }) =>
            updateAsrProviderSecret(providerId, apiKey),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queryKeys.asrCatalog });
            queryClient.invalidateQueries({ queryKey: queryKeys.asrActive });
        },
    });
}

export function useDeleteAsrProviderSecret() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (providerId: string) => deleteAsrProviderSecret(providerId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: queryKeys.asrCatalog });
            queryClient.invalidateQueries({ queryKey: queryKeys.asrActive });
        },
    });
}

export function useTestActiveAsrSettings() {
    return useMutation({
        mutationFn: testActiveAsrSettings,
    });
}

export function useTestAsrProviderSettings() {
    return useMutation({
        mutationFn: ({
            providerId,
            modelId,
            languageHints,
        }: {
            providerId: string;
            modelId: string;
            languageHints?: string[];
        }) => testAsrProviderSettings(providerId, modelId, languageHints),
    });
}
