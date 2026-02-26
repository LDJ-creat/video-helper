import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type { SearchResponse } from "../contracts/searchTypes";
import { config } from "../config";

export async function fetchSearchResults(
    query: string,
    cursor?: string,
    limit = 20
): Promise<SearchResponse> {
    const baseUrl = config.apiBaseUrl || window.location.origin;
    const url = new URL(endpoints.search(), baseUrl);
    url.searchParams.set("query", query);
    if (cursor) {
        url.searchParams.set("cursor", cursor);
    }
    url.searchParams.set("limit", limit.toString());

    return apiFetch<SearchResponse>(url);
}
