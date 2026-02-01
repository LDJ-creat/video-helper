"use client";

import { HealthBanner } from "@/components/HealthBanner";
import { useCreateJobFromUrl, useCreateJobFromUpload } from "@/lib/api/jobCreationQueries";
import type { SourceType } from "@/lib/contracts/jobCreation";
import { useState } from "react";
import type { ApiErrorEnvelope } from "@/lib/api/apiClient";

type TabType = "url" | "upload";

export default function IngestPage() {
    const [activeTab, setActiveTab] = useState<TabType>("url");

    return (
        <div className="mx-auto max-w-2xl space-y-6 p-6">
            <div>
                <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">
                    创建视频分析
                </h1>
                <p className="mt-2 text-zinc-600 dark:text-zinc-400">
                    通过粘贴链接或上传文件来创建新的分析任务
                </p>
            </div>

            <HealthBanner />

            <div className="rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
                {/* Tab Headers */}
                <div className="flex border-b border-zinc-200 dark:border-zinc-800">
                    <button
                        onClick={() => setActiveTab("url")}
                        className={`flex-1 border-b-2 px-6 py-3 text-sm font-medium transition-colors ${activeTab === "url"
                                ? "border-zinc-900 text-zinc-900 dark:border-zinc-50 dark:text-zinc-50"
                                : "border-transparent text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300"
                            }`}
                    >
                        粘贴链接
                    </button>
                    <button
                        onClick={() => setActiveTab("upload")}
                        className={`flex-1 border-b-2 px-6 py-3 text-sm font-medium transition-colors ${activeTab === "upload"
                                ? "border-zinc-900 text-zinc-900 dark:border-zinc-50 dark:text-zinc-50"
                                : "border-transparent text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-300"
                            }`}
                    >
                        上传文件
                    </button>
                </div>

                {/* Tab Panels */}
                <div className="p-6">
                    {activeTab === "url" ? <UrlForm /> : <UploadForm />}
                </div>
            </div>
        </div>
    );
}

function UrlForm() {
    const [sourceType, setSourceType] = useState<Exclude<SourceType, "upload">>("youtube");
    const [sourceUrl, setSourceUrl] = useState("");
    const [title, setTitle] = useState("");
    const mutation = useCreateJobFromUrl();

    const isValidUrl = (url: string) => {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    };

    const canSubmit = sourceUrl.trim() !== "" && isValidUrl(sourceUrl);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!canSubmit) return;

        mutation.mutate({
            sourceType,
            sourceUrl: sourceUrl.trim(),
            title: title.trim() || undefined,
        });
    };

    const errorMessage = mutation.error
        ? getErrorMessage(mutation.error)
        : null;

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            <div>
                <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-50">
                    视频来源
                </label>
                <div className="mt-2 flex gap-4">
                    <label className="flex items-center gap-2">
                        <input
                            type="radio"
                            value="youtube"
                            checked={sourceType === "youtube"}
                            onChange={(e) => setSourceType(e.target.value as "youtube")}
                            className="h-4 w-4 text-zinc-900 focus:ring-zinc-900 dark:text-zinc-50 dark:focus:ring-zinc-50"
                        />
                        <span className="text-sm text-zinc-700 dark:text-zinc-300">YouTube</span>
                    </label>
                    <label className="flex items-center gap-2">
                        <input
                            type="radio"
                            value="bilibili"
                            checked={sourceType === "bilibili"}
                            onChange={(e) => setSourceType(e.target.value as "bilibili")}
                            className="h-4 w-4 text-zinc-900 focus:ring-zinc-900 dark:text-zinc-50 dark:focus:ring-zinc-50"
                        />
                        <span className="text-sm text-zinc-700 dark:text-zinc-300">Bilibili</span>
                    </label>
                </div>
            </div>

            <div>
                <label htmlFor="url" className="block text-sm font-medium text-zinc-900 dark:text-zinc-50">
                    视频链接 *
                </label>
                <input
                    type="text"
                    id="url"
                    value={sourceUrl}
                    onChange={(e) => setSourceUrl(e.target.value)}
                    placeholder="https://..."
                    className="mt-2 block w-full rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 placeholder-zinc-400 focus:border-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50 dark:placeholder-zinc-500 dark:focus:border-zinc-50 dark:focus:ring-zinc-50"
                />
                {sourceUrl && !isValidUrl(sourceUrl) && (
                    <p className="mt-1 text-sm text-red-600 dark:text-red-400">
                        请输入有效的 URL
                    </p>
                )}
            </div>

            <div>
                <label htmlFor="title" className="block text-sm font-medium text-zinc-900 dark:text-zinc-50">
                    标题（可选）
                </label>
                <input
                    type="text"
                    id="title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="为项目设置自定义标题"
                    className="mt-2 block w-full rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 placeholder-zinc-400 focus:border-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50 dark:placeholder-zinc-500 dark:focus:border-zinc-50 dark:focus:ring-zinc-50"
                />
            </div>

            {errorMessage && (
                <div className="rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950">
                    <p className="text-sm text-red-900 dark:text-red-100">{errorMessage}</p>
                </div>
            )}

            <button
                type="submit"
                disabled={!canSubmit || mutation.isPending}
                className="w-full rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus:ring-zinc-50"
            >
                {mutation.isPending ? "创建中..." : "创建分析任务"}
            </button>
        </form>
    );
}

function UploadForm() {
    const [file, setFile] = useState<File | null>(null);
    const [title, setTitle] = useState("");
    const mutation = useCreateJobFromUpload();

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        if (selectedFile) {
            // Check if it's a video file
            if (!selectedFile.type.startsWith("video/")) {
                alert("请选择视频文件");
                return;
            }
            setFile(selectedFile);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!file) return;

        mutation.mutate({
            file,
            title: title.trim() || undefined,
        });
    };

    const errorMessage = mutation.error
        ? getErrorMessage(mutation.error)
        : null;

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            <div>
                <label htmlFor="file" className="block text-sm font-medium text-zinc-900 dark:text-zinc-50">
                    选择视频文件 *
                </label>
                <div className="mt-2">
                    <input
                        type="file"
                        id="file"
                        accept="video/*"
                        onChange={handleFileChange}
                        className="block w-full text-sm text-zinc-900 file:mr-4 file:rounded-md file:border-0 file:bg-zinc-100 file:px-4 file:py-2 file:text-sm file:font-medium file:text-zinc-900 hover:file:bg-zinc-200 dark:text-zinc-50 dark:file:bg-zinc-800 dark:file:text-zinc-50 dark:hover:file:bg-zinc-700"
                    />
                    {file && (
                        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
                            已选择: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
                        </p>
                    )}
                </div>
            </div>

            <div>
                <label htmlFor="upload-title" className="block text-sm font-medium text-zinc-900 dark:text-zinc-50">
                    标题（可选）
                </label>
                <input
                    type="text"
                    id="upload-title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="为项目设置自定义标题"
                    className="mt-2 block w-full rounded-md border border-zinc-300 px-3 py-2 text-zinc-900 placeholder-zinc-400 focus:border-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50 dark:placeholder-zinc-500 dark:focus:border-zinc-50 dark:focus:ring-zinc-50"
                />
            </div>

            {errorMessage && (
                <div className="rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950">
                    <p className="text-sm text-red-900 dark:text-red-100">{errorMessage}</p>
                </div>
            )}

            <button
                type="submit"
                disabled={!file || mutation.isPending}
                className="w-full rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus:ring-zinc-50"
            >
                {mutation.isPending ? "上传中..." : "创建分析任务"}
            </button>
        </form>
    );
}

function getErrorMessage(error: unknown): string {
    // Try to parse as error envelope
    if (error && typeof error === "object" && "error" in error) {
        const envelope = error as ApiErrorEnvelope;
        return envelope.error.message || "发生未知错误";
    }

    if (error instanceof Error) {
        return error.message;
    }

    return "发生未知错误";
}
