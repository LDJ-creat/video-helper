import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "./healthApi";

/**
 * React Query hook for health check
 * - Caches for 30 seconds
 * - Retries on failure (3 times with 1s delay)
 * - Automatically triggered when component mounts
 */
export function useHealthQuery() {
    return useQuery({
        queryKey: ["health"],
        queryFn: fetchHealth,
        staleTime: 30000, // 30s - health check doesn't change frequently
        retry: 3,
        retryDelay: 1000,
    });
}
