import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";
import {
    deleteAsrProviderSecret,
    fetchActiveAsrSettings,
    fetchAsrCatalog,
    fetchAsrRemoteModels,
    addCustomAsrModel,
    deleteCustomAsrModel,
    testActiveAsrSettings,
    testAsrProviderSettings,
    updateActiveAsrSettings,
    updateAsrProviderSecret,
} from "./asrSettingsApi";
import type { AddCustomAsrModelRequest, UpdateAsrActiveRequest } from "../contracts/asrSettingsTypes";

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

export function useRemoteAsrModels(providerId: string, enabled: boolean) {
    return useQuery({
        queryKey: queryKeys.asrRemoteModels(providerId),
        queryFn: () => fetchAsrRemoteModels(providerId),
        enabled: Boolean(providerId) && enabled,
    });
}

export function useAddCustomAsrModel() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ providerId, request }: { providerId: string; request: AddCustomAsrModelRequest }) =>
            addCustomAsrModel(providerId, request),
        onSuccess: (_data, { providerId }) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.asrCatalog });
            queryClient.invalidateQueries({ queryKey: queryKeys.asrRemoteModels(providerId) });
        },
    });
}

export function useDeleteCustomAsrModel() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ providerId, modelId }: { providerId: string; modelId: string }) =>
            deleteCustomAsrModel(providerId, modelId),
        onSuccess: (_data, { providerId }) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.asrCatalog });
            queryClient.invalidateQueries({ queryKey: queryKeys.asrRemoteModels(providerId) });
        },
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
        onSuccess: (_data, { providerId }) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.asrCatalog });
            queryClient.invalidateQueries({ queryKey: queryKeys.asrActive });
            queryClient.invalidateQueries({ queryKey: queryKeys.asrRemoteModels(providerId) });
        },
    });
}

export function useDeleteAsrProviderSecret() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (providerId: string) => deleteAsrProviderSecret(providerId),
        onSuccess: (_data, providerId) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.asrCatalog });
            queryClient.invalidateQueries({ queryKey: queryKeys.asrActive });
            queryClient.invalidateQueries({ queryKey: queryKeys.asrRemoteModels(providerId) });
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
        }: {
            providerId: string;
            modelId: string;
        }) => testAsrProviderSettings(providerId, modelId),
    });
}
