import { useInfiniteQuery, useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";
import { fetchProjects, fetchProjectDetail, deleteProject } from "./projectApi";
import type { ProjectsListResponse } from "../contracts/projectTypes";

export function useProjects() {
    return useInfiniteQuery({
        queryKey: queryKeys.projects,
        queryFn: ({ pageParam }: { pageParam: string | undefined }) => fetchProjects(pageParam),
        initialPageParam: undefined as string | undefined,
        getNextPageParam: (lastPage: ProjectsListResponse) => lastPage.nextCursor ?? undefined,
    });
}

export function useProjectDetail(projectId: string) {
    return useQuery({
        queryKey: queryKeys.project(projectId),
        queryFn: () => fetchProjectDetail(projectId),
    });
}

export function useDeleteProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (projectId: string) => deleteProject(projectId),
        onSuccess: () => {
            // Invalidate projects list to refetch
            queryClient.invalidateQueries({ queryKey: queryKeys.projects });
        },
    });
}
