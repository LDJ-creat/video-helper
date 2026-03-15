"use client";

import { HealthBanner } from "@/components/HealthBanner";
import { useCreateJobFromUrl, useCreateJobFromUpload } from "@/lib/api/jobCreationQueries";
import { useCookiesStatus, useUploadCookies } from "@/lib/api/cookiesQueries";
import { useState, useRef, useCallback } from "react";
import type { ApiErrorEnvelope } from "@/lib/api/apiClient";
import { useLocale, useTranslations } from "next-intl";

type TabType = "url" | "upload";

export default function IngestPage() {
    const t = useTranslations("Ingest");
    const [activeTab, setActiveTab] = useState<TabType>("url");

    return (
        <div className="mx-auto max-w-3xl xl:max-w-5xl space-y-8 xl:space-y-10 p-6 sm:p-10 xl:p-12">
            <div className="space-y-2 xl:space-y-3">
                <h1 className="text-3xl xl:text-4xl font-bold tracking-tight text-stone-900">
                    {t("title")}
                </h1>
                <p className="text-lg xl:text-xl text-stone-600">
                    {t("subtitle")}
                </p>
            </div>

            <HealthBanner />

            {/* Cozy Card */}
            <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm transition-shadow hover:shadow-md">
                {/* Tab Headers */}
                <div className="flex border-b border-stone-100 bg-stone-50/50">
                    <button
                        onClick={() => setActiveTab("url")}
                        className={`flex-1 py-4 xl:py-5 text-sm xl:text-base font-medium transition-all ${activeTab === "url"
                            ? "border-b-2 border-stone-800 bg-white text-stone-900 shadow-sm"
                            : "text-stone-500 hover:bg-stone-100 hover:text-stone-700"
                            }`}
                    >
                        {t("tabUrl")}
                    </button>
                    <button
                        onClick={() => setActiveTab("upload")}
                        className={`flex-1 py-4 xl:py-5 text-sm xl:text-base font-medium transition-all ${activeTab === "upload"
                            ? "border-b-2 border-stone-800 bg-white text-stone-900 shadow-sm"
                            : "text-stone-500 hover:bg-stone-100 hover:text-stone-700"
                            }`}
                    >
                        {t("tabUpload")}
                    </button>
                </div>

                {/* Tab Panels */}
                <div className="p-8">
                    {activeTab === "url" ? <UrlForm /> : <UploadForm />}
                </div>
            </div>
        </div>
    );
}

// ─── Reusable DnD hook ────────────────────────────────────────────────────────

function useDragAndDrop(onDrop: (file: File) => void, accept?: (file: File) => boolean) {
    const [isDragging, setIsDragging] = useState(false);
    const dragCounterRef = useRef(0);

    const handleDragEnter = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounterRef.current++;
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounterRef.current--;
        if (dragCounterRef.current === 0) setIsDragging(false);
    }, []);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = "copy";
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounterRef.current = 0;
        setIsDragging(false);

        const file = e.dataTransfer.files?.[0];
        if (!file) return;
        if (accept && !accept(file)) return;
        onDrop(file);
    }, [onDrop, accept]);

    return { isDragging, handleDragEnter, handleDragLeave, handleDragOver, handleDrop };
}

// ─── Cookies Upload Section ─────────────────────────────────────────────────

function CookiesUploadSection() {
    const t = useTranslations("Ingest.cookies");
    const [expanded, setExpanded] = useState(false);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const { data: status } = useCookiesStatus();
    const mutation = useUploadCookies();

    const hasFile = status?.hasFile ?? false;

    const doUpload = useCallback((file: File) => {
        setSuccessMsg(null);
        mutation.mutate(file, {
            onSuccess: () => {
                setSuccessMsg(t("uploadSuccess"));
                if (fileInputRef.current) fileInputRef.current.value = "";
            },
        });
    }, [mutation, t]);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) doUpload(file);
    };

    const acceptCookie = useCallback((file: File) => {
        return file.name.endsWith(".txt") || file.type === "text/plain";
    }, []);

    const { isDragging, handleDragEnter, handleDragLeave, handleDragOver, handleDrop } =
        useDragAndDrop(doUpload, acceptCookie);

    const errorMsg = mutation.error ? t("uploadError") : null;

    return (
        <div className="rounded-xl border border-stone-200 bg-stone-50/60 overflow-hidden">
            {/* Collapsible header */}
            <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="flex w-full items-center justify-between px-4 py-3 xl:px-6 xl:py-4 text-left transition-colors hover:bg-stone-100"
            >
                <span className="flex items-center gap-2 text-sm xl:text-base font-medium text-stone-700">
                    {/* Cookie SVG icon */}
                    <svg className="w-4 h-4 text-stone-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 3C7.03 3 3 7.03 3 12s4.03 9 9 9 9-4.03 9-9" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 3.5A8.96 8.96 0 0121 9.5M9 9h.01M12 14h.01M15 11h.01" />
                    </svg>
                    {t("sectionTitle")}
                </span>
                <div className="flex items-center gap-2 xl:gap-3">
                    <span
                        className={`rounded-full px-2 py-0.5 xl:px-3 xl:py-1 text-xs xl:text-sm font-medium ${hasFile
                            ? "bg-green-100 text-green-700"
                            : "bg-stone-200 text-stone-500"
                            }`}
                    >
                        {hasFile ? t("statusConfigured") : t("statusNotConfigured")}
                    </span>
                    <svg
                        className={`h-4 w-4 xl:h-5 xl:w-5 text-stone-400 transition-transform ${expanded ? "rotate-180" : ""}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                </div>
            </button>

            {/* Expanded body */}
            {expanded && (
                <div className="border-t border-stone-200 px-4 pb-4 pt-3 space-y-4">
                    {/* Description */}
                    <p className="text-sm text-stone-600 leading-relaxed">
                        {t("description")}
                    </p>

                    {/* Guide */}
                    <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2.5 text-sm text-amber-800 leading-relaxed flex gap-2">
                        <svg className="w-4 h-4 mt-0.5 shrink-0 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 18h.01M12 2a10 10 0 100 20A10 10 0 0012 2zm0 14v-4m0-4V8" />
                        </svg>
                        <span>{t("guide")}</span>
                    </div>

                    {/* Current file info */}
                    {hasFile && status?.fileName && (
                        <p className="text-xs text-stone-500">
                            {t("currentFile", { fileName: status.fileName })}
                        </p>
                    )}

                    {/* DnD + click file upload zone */}
                    <div
                        onDragEnter={handleDragEnter}
                        onDragLeave={handleDragLeave}
                        onDragOver={handleDragOver}
                        onDrop={handleDrop}
                        onClick={() => fileInputRef.current?.click()}
                        className={`flex flex-col items-center justify-center gap-2 xl:gap-4 rounded-lg xl:rounded-xl border-2 border-dashed cursor-pointer py-6 px-4 xl:min-h-[250px] xl:px-8 transition-colors ${isDragging
                            ? "border-blue-400 bg-blue-50"
                            : "border-stone-300 bg-white hover:bg-stone-50 hover:border-stone-400"
                            }`}
                    >
                        <svg className={`w-8 h-8 xl:w-12 xl:h-12 ${isDragging ? "text-blue-400" : "text-stone-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <p className="text-sm xl:text-lg text-stone-600">
                            {isDragging ? "松开以上传" : t("labelFile")}
                        </p>
                        <p className="text-xs xl:text-sm text-stone-400">拖拽或点击，支持 .txt 格式</p>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".txt"
                            onChange={handleFileChange}
                            disabled={mutation.isPending}
                            className="hidden"
                        />
                    </div>

                    {/* Feedback */}
                    {mutation.isPending && (
                        <p className="text-sm text-stone-500">{t("uploading")}</p>
                    )}
                    {successMsg && (
                        <p className="text-sm text-green-600">{successMsg}</p>
                    )}
                    {errorMsg && (
                        <p className="text-sm text-red-500">{errorMsg}</p>
                    )}
                </div>
            )}
        </div>
    );
}

// ─── URL Form ───────────────────────────────────────────────────────────────

function UrlForm() {
    const t = useTranslations("Ingest.urlForm");
    const locale = useLocale();
    const [sourceUrl, setSourceUrl] = useState("");
    const [title, setTitle] = useState("");
    const [outputLanguage, setOutputLanguage] = useState(locale === "zh" ? "zh-Hans" : "en");
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
            sourceUrl: sourceUrl.trim(),
            title: title.trim() || undefined,
            outputLanguage: outputLanguage.trim() || undefined,
        });
    };

    const errorMessage = mutation.error
        ? getErrorMessage(mutation.error)
        : null;

    return (
        <form onSubmit={handleSubmit} className="space-y-6 xl:space-y-8">
            <div className="space-y-2 xl:space-y-3">
                <label htmlFor="url" className="block text-sm xl:text-base font-medium text-stone-700">
                    {t("labelUrl")} <span className="text-red-500">*</span>
                </label>
                <input
                    type="text"
                    id="url"
                    value={sourceUrl}
                    onChange={(e) => setSourceUrl(e.target.value)}
                    placeholder={t("placeholderUrl") || "https://..."}
                    className="block w-full rounded-lg border border-stone-200 bg-white px-4 py-3 xl:px-5 xl:py-4 xl:text-base text-stone-900 placeholder-stone-400 focus:border-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-200"
                />
                {sourceUrl && !isValidUrl(sourceUrl) && (
                    <p className="text-sm text-red-500">
                        {t("invalidUrl")}
                    </p>
                )}
            </div>

            <div className="space-y-2 xl:space-y-3">
                <label htmlFor="title" className="block text-sm xl:text-base font-medium text-stone-700">
                    {t("labelTitle")}
                </label>
                <input
                    type="text"
                    id="title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder={t("placeholderTitle")}
                    className="block w-full rounded-lg border border-stone-200 bg-white px-4 py-3 xl:px-5 xl:py-4 xl:text-base text-stone-900 placeholder-stone-400 focus:border-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-200"
                />
            </div>

            <div className="space-y-2 xl:space-y-3">
                <label htmlFor="outputLanguage" className="block text-sm xl:text-base font-medium text-stone-700">
                    {t("labelLang")}
                </label>
                <select
                    id="outputLanguage"
                    value={outputLanguage}
                    onChange={(e) => setOutputLanguage(e.target.value)}
                    className="block w-full rounded-lg border border-stone-200 bg-white px-4 py-3 xl:px-5 xl:py-4 xl:text-base text-stone-900 focus:border-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-200"
                >
                    <option value="zh-Hans">{t("options.zhHans")}</option>
                    <option value="en">{t("options.en")}</option>
                    <option value="auto">{t("options.auto")}</option>
                </select>
                <p className="text-sm text-stone-500">
                    {t("langDesc")}
                </p>
            </div>

            {/* Cookies upload section */}
            <CookiesUploadSection />

            {errorMessage && (
                <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">
                    {errorMessage}
                </div>
            )}

            <button
                type="submit"
                disabled={!canSubmit || mutation.isPending}
                className="w-full rounded-lg bg-stone-800 px-4 py-3 xl:py-4 text-base xl:text-lg font-medium text-white transition-all hover:bg-stone-900 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-stone-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
                {mutation.isPending ? t("submitting") : t("submit")}
            </button>
        </form>
    );
}

function UploadForm() {
    const t = useTranslations("Ingest.uploadForm");
    const tUrl = useTranslations("Ingest.urlForm");
    const locale = useLocale();
    const tOptions = useTranslations("Ingest.urlForm.options");

    const [file, setFile] = useState<File | null>(null);
    const [title, setTitle] = useState("");
    const [outputLanguage, setOutputLanguage] = useState(locale === "zh" ? "zh-Hans" : "en");
    const mutation = useCreateJobFromUpload();
    const fileInputRef = useRef<HTMLInputElement>(null);

    const validateAndSetFile = useCallback((f: File) => {
        if (!f.type.startsWith("video/")) {
            alert(t("selectFileError"));
            return;
        }
        setFile(f);
    }, [t]);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        if (selectedFile) validateAndSetFile(selectedFile);
    };

    const acceptVideo = useCallback((f: File) => f.type.startsWith("video/"), []);

    const { isDragging, handleDragEnter, handleDragLeave, handleDragOver, handleDrop } =
        useDragAndDrop(validateAndSetFile, acceptVideo);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!file) return;

        mutation.mutate({
            file,
            title: title.trim() || undefined,
            outputLanguage: outputLanguage.trim() || undefined,
        });
    };

    const errorMessage = mutation.error
        ? getErrorMessage(mutation.error)
        : null;

    return (
        <form onSubmit={handleSubmit} className="space-y-6">
            {/* DnD Video Upload Zone */}
            <div className="space-y-2">
                <label className="block text-sm font-medium text-stone-700">
                    {t("labelFile")} <span className="text-red-500">*</span>
                </label>
                <div
                    onDragEnter={handleDragEnter}
                    onDragLeave={handleDragLeave}
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`mt-2 flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed cursor-pointer px-6 py-12 transition-all ${isDragging
                        ? "border-blue-400 bg-blue-50 scale-[1.01]"
                        : file
                            ? "border-green-300 bg-green-50"
                            : "border-stone-200 bg-stone-50 hover:bg-stone-100 hover:border-stone-300"
                        }`}
                >
                    {file ? (
                        <>
                            <div className="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center">
                                <svg className="w-7 h-7 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                </svg>
                            </div>
                            <div className="text-center">
                                <p className="text-sm font-semibold text-stone-800">{file.name}</p>
                                <p className="text-xs text-stone-500 mt-0.5">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                            </div>
                            <button
                                type="button"
                                onClick={(e) => { e.stopPropagation(); setFile(null); if (fileInputRef.current) fileInputRef.current.value = ""; }}
                                className="text-xs text-stone-400 hover:text-red-500 transition-colors"
                            >
                                更换文件
                            </button>
                        </>
                    ) : (
                        <>
                            <div className={`w-14 h-14 rounded-full flex items-center justify-center ${isDragging ? "bg-blue-100" : "bg-stone-100"}`}>
                                <svg className={`w-7 h-7 ${isDragging ? "text-blue-500" : "text-stone-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                                </svg>
                            </div>
                            <div className="text-center">
                                <p className="text-sm font-semibold text-stone-700">
                                    {isDragging ? "松开以上传视频" : "拖拽视频到此处"}
                                </p>
                                <p className="text-xs text-stone-400 mt-1">支持 MP4、MKV、AVI 等常见格式，或点击选择</p>
                            </div>
                        </>
                    )}
                    <input
                        ref={fileInputRef}
                        type="file"
                        id="file"
                        accept="video/*"
                        onChange={handleFileChange}
                        className="hidden"
                    />
                </div>
            </div>

            <div className="space-y-2 xl:space-y-3">
                <label htmlFor="upload-title" className="block text-sm xl:text-base font-medium text-stone-700">
                    {tUrl("labelTitle")}
                </label>
                <input
                    type="text"
                    id="upload-title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder={tUrl("placeholderTitle")}
                    className="block w-full rounded-lg border border-stone-200 bg-white px-4 py-3 xl:px-5 xl:py-4 xl:text-base text-stone-900 placeholder-stone-400 focus:border-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-200"
                />
            </div>

            <div className="space-y-2 xl:space-y-3">
                <label htmlFor="upload-outputLanguage" className="block text-sm xl:text-base font-medium text-stone-700">
                    {tUrl("labelLang")}
                </label>
                <select
                    id="upload-outputLanguage"
                    value={outputLanguage}
                    onChange={(e) => setOutputLanguage(e.target.value)}
                    className="block w-full rounded-lg border border-stone-200 bg-white px-4 py-3 xl:px-5 xl:py-4 xl:text-base text-stone-900 focus:border-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-200"
                >
                    <option value="zh-Hans">{tOptions("zhHans")}</option>
                    <option value="en">{tOptions("en")}</option>
                    <option value="auto">{tOptions("auto")}</option>
                </select>
                <p className="text-sm text-stone-500">
                    {tUrl("langDesc")}
                </p>
            </div>

            {errorMessage && (
                <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">
                    {errorMessage}
                </div>
            )}

            <button
                type="submit"
                disabled={!file || mutation.isPending}
                className="w-full rounded-lg bg-stone-800 px-4 py-3 xl:py-4 text-base xl:text-lg font-medium text-white transition-all hover:bg-stone-900 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-stone-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
                {mutation.isPending ? t("submitting") : t("submit")}
            </button>
        </form>
    );
}

function getErrorMessage(error: unknown): string {
    if (error && typeof error === "object" && "error" in error) {
        const envelope = error as ApiErrorEnvelope;
        return envelope.error.message || "发生未知错误";
    }

    if (error instanceof Error) {
        return error.message;
    }

    return "发生未知错误";
}
