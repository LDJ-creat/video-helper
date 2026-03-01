import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import { config } from "../config";

export interface CookiesStatusResponse {
    hasFile: boolean;
    fileName: string | null;
    updatedAtMs: number | null;
}

export interface OkResponse {
    ok: boolean;
}

export async function uploadCookiesFile(file: File): Promise<OkResponse> {
    const form = new FormData();
    form.append("file", file);
    const url = `${config.apiBaseUrl}${endpoints.ytdlpCookiesUpload()}`;
    return apiFetch<OkResponse>(url, {
        method: "POST",
        body: form,
    });
}

export async function getCookiesStatus(): Promise<CookiesStatusResponse> {
    const url = `${config.apiBaseUrl}${endpoints.ytdlpCookiesStatus()}`;
    return apiFetch<CookiesStatusResponse>(url);
}
