import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";
import { fetchSettings, updateSettings } from "./settingsApi";

export function useSettings() {
    return useQuery({
        queryKey: queryKeys.settings,
        queryFn: fetchSettings,
    });
}

export function useUpdateSettings() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: updateSettings,
        onSuccess: () => {
            // Invalidate settings query to refetch
            queryClient.invalidateQueries({ queryKey: queryKeys.settings });
        },
    });
}
