import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { uploadCookiesFile, getCookiesStatus } from "./cookiesApi";

export const COOKIES_STATUS_QUERY_KEY = ["ytdlp", "cookies", "status"];

export function useCookiesStatus() {
    return useQuery({
        queryKey: COOKIES_STATUS_QUERY_KEY,
        queryFn: getCookiesStatus,
        staleTime: 30_000,
    });
}

export function useUploadCookies() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (file: File) => uploadCookiesFile(file),
        onSuccess: () => {
            // Invalidate status so UI refreshes to "configured"
            queryClient.invalidateQueries({ queryKey: COOKIES_STATUS_QUERY_KEY });
        },
    });
}
