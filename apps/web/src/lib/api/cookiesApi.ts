import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";

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
    return apiFetch<OkResponse>(endpoints.ytdlpCookiesUpload(), {
        method: "POST",
        body: form,
    });
}

export async function getCookiesStatus(): Promise<CookiesStatusResponse> {
    return apiFetch<CookiesStatusResponse>(endpoints.ytdlpCookiesStatus());
}
