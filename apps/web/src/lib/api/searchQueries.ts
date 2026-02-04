import { useInfiniteQuery } from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";
import { fetchSearchResults } from "./searchApi";
import type { SearchResponse } from "../contracts/searchTypes";

export function useSearch(query: string, enabled = true) {
    return useInfiniteQuery({
        queryKey: queryKeys.search(query),
        queryFn: ({ pageParam }: { pageParam: string | undefined }) =>
            fetchSearchResults(query, pageParam),
        initialPageParam: undefined as string | undefined,
        getNextPageParam: (lastPage: SearchResponse) => lastPage.nextCursor ?? undefined,
        enabled: enabled && query.trim().length > 0, // Only fetch if query is non-empty
    });
}
