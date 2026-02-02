import { apiFetch } from "./apiClient";
import { endpoints } from "./endpoints";
import type { ProjectsListResponse, ProjectDetailResponse } from "../contracts/projectTypes";

export async function fetchProjects(cursor?: string): Promise<ProjectsListResponse> {
    const url = new URL(endpoints.projects(), window.location.origin);
    if (cursor) {
        url.searchParams.set("cursor", cursor);
    }
    return apiFetch<ProjectsListResponse>(url);
}

export async function fetchProjectDetail(projectId: string): Promise<ProjectDetailResponse> {
    return apiFetch<ProjectDetailResponse>(endpoints.project(projectId));
}

export async function deleteProject(projectId: string): Promise<void> {
    await apiFetch<void>(endpoints.deleteProject(projectId), {
        method: "DELETE",
    });
}
