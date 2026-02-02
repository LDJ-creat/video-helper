"use client";

import { useProjects, useDeleteProject } from "@/lib/api/projectQueries";
import Link from "next/link";

export default function ProjectsPage() {
    const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading, error } = useProjects();
    const deleteMutation = useDeleteProject();

    const handleDelete = async (projectId: string, projectTitle: string) => {
        const confirmed = window.confirm(`确定要删除项目 "${projectTitle}" 吗？此操作不可撤销。`);
        if (!confirmed) return;

        try {
            await deleteMutation.mutateAsync(projectId);
            alert("项目已成功删除");
        } catch (err) {
            const errorMessage = (err as any)?.error?.message || "删除失败";
            const shouldRetry = window.confirm(`${errorMessage}\n\n是否重试？`);
            if (shouldRetry) {
                handleDelete(projectId, projectTitle);
            }
        }
    };

    if (isLoading) {
        return <main className="p-6"><p>加载中...</p></main>;
    }

    if (error) {
        return <main className="p-6"><p className="text-red-600">加载失败: {String(error)}</p></main>;
    }

    const projects = data?.pages.flatMap((page) => page.items) ?? [];

    return (
        <main className="p-6">
            <h1 className="text-2xl font-semibold mb-4">Projects</h1>

            {projects.length === 0 && <p className="text-gray-500">暂无项目</p>}

            <div className="grid gap-4">
                {projects.map((project) => (
                    <div key={project.projectId} className="border p-4 rounded flex justify-between items-start">
                        <div className="flex-1">
                            <h2 className="text-lg font-medium">{project.title}</h2>
                            <p className="text-sm text-gray-600">来源: {project.sourceType}</p>
                            <p className="text-sm text-gray-600">
                                更新时间: {new Date(project.updatedAtMs).toLocaleString()}
                            </p>
                            <Link
                                href={`/projects/${project.projectId}`}
                                className="text-blue-600 hover:underline mt-2 inline-block"
                            >
                                查看详情
                            </Link>
                        </div>

                        <button
                            onClick={() => handleDelete(project.projectId, project.title)}
                            disabled={deleteMutation.isPending}
                            className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:bg-gray-400"
                        >
                            {deleteMutation.isPending ? "删除中..." : "删除"}
                        </button>
                    </div>
                ))}
            </div>

            {hasNextPage && (
                <button
                    onClick={() => fetchNextPage()}
                    disabled={isFetchingNextPage}
                    className="mt-4 px-4 py-2 bg-blue-600 text-white rounded disabled:bg-gray-400"
                >
                    {isFetchingNextPage ? "加载中..." : "加载更多"}
                </button>
            )}
        </main>
    );
}
