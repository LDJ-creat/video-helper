"use client";

import { useProjectDetail, useDeleteProject } from "@/lib/api/projectQueries";
import { use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function ProjectDetailPage({
    params,
}: {
    params: Promise<{ projectId: string }>;
}) {
    const { projectId } = use(params);
    const { data: project, isLoading, error } = useProjectDetail(projectId);
    const deleteMutation = useDeleteProject();
    const router = useRouter();

    const handleDelete = async () => {
        if (!project) return;

        const confirmed = window.confirm(`确定要删除项目 "${project.title}" 吗？此操作不可撤销。`);
        if (!confirmed) return;

        try {
            await deleteMutation.mutateAsync(projectId);
            alert("项目已成功删除");
            router.push("/projects");
        } catch (err) {
            const errorMessage = (err as any)?.error?.message || "删除失败";
            const shouldRetry = window.confirm(`${errorMessage}\n\n是否重试？`);
            if (shouldRetry) {
                handleDelete();
            }
        }
    };

    if (isLoading) {
        return <main className="p-6"><p>加载中...</p></main>;
    }

    if (error) {
        return <main className="p-6"><p className="text-red-600">加载失败: {String(error)}</p></main>;
    }

    if (!project) {
        return <main className="p-6"><p>项目未找到</p></main>;
    }

    const hasResult = !!project.latestResultId;

    return (
        <main className="p-6">
            <h1 className="text-2xl font-semibold mb-4">{project.title}</h1>

            <div className="space-y-2 mb-6">
                <p><strong>项目 ID:</strong> {project.projectId}</p>
                <p><strong>来源类型:</strong> {project.sourceType}</p>
                {project.sourceUrl && <p><strong>来源 URL:</strong> {project.sourceUrl}</p>}
                <p><strong>创建时间:</strong> {new Date(project.createdAtMs).toLocaleString()}</p>
                <p><strong>更新时间:</strong> {new Date(project.updatedAtMs).toLocaleString()}</p>
                <p><strong>最新结果 ID:</strong> {project.latestResultId || "无"}</p>
            </div>

            <div className="flex gap-4">
                {hasResult ? (
                    <Link
                        href={`/projects/${project.projectId}/results`}
                        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                    >
                        打开结果
                    </Link>
                ) : (
                    <div className="text-gray-500">
                        <p>结果未就绪</p>
                        {/* TODO: 可选择性跳转到 Jobs 页面查看进度 */}
                    </div>
                )}

                <button
                    onClick={handleDelete}
                    disabled={deleteMutation.isPending}
                    className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:bg-gray-400"
                >
                    {deleteMutation.isPending ? "删除中..." : "删除项目"}
                </button>
            </div>
        </main>
    );
}
