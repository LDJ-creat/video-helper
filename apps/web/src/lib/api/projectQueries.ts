import {
    keepPreviousData,
    useInfiniteQuery,
    useQuery,
    useMutation,
    useQueryClient,
} from "@tanstack/react-query";
import { queryKeys } from "./queryKeys";
import {
    fetchProjects,
    fetchProjectDetail,
    deleteProject,
    patchProjectCategory,
    batchUpdateProjectCategory,
} from "./projectApi";
import type { ProjectsListResponse } from "../contracts/projectTypes";

export function useProjects(categoryId?: string | null) {
    return useInfiniteQuery({
        queryKey: queryKeys.projects(categoryId),
        queryFn: ({ pageParam }: { pageParam: string | undefined }) =>
            fetchProjects(pageParam, categoryId),
        initialPageParam: undefined as string | undefined,
        getNextPageParam: (lastPage: ProjectsListResponse) => lastPage.nextCursor ?? undefined,
        placeholderData: keepPreviousData,
        staleTime: 30_000,
    });
}

export function usePatchProjectCategory() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            projectId,
            categoryId,
        }: {
            projectId: string;
            categoryId: string;
        }) => patchProjectCategory(projectId, { categoryId }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["projects"] });
            queryClient.invalidateQueries({ queryKey: queryKeys.categories });
        },
    });
}

export function useBatchUpdateProjectCategory() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: batchUpdateProjectCategory,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["projects"] });
            queryClient.invalidateQueries({ queryKey: queryKeys.categories });
        },
    });
}

export function useProjectDetail(projectId: string, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: queryKeys.project(projectId),
        queryFn: () => fetchProjectDetail(projectId),
        enabled: options?.enabled ?? true,
    });
}

export function useDeleteProject() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (projectId: string) => deleteProject(projectId),
        onSuccess: () => {
            // Invalidate projects list to refetch
            queryClient.invalidateQueries({ queryKey: ["projects"] });
        },
    });
}
