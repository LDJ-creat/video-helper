"use client";

import { HealthBanner } from "@/components/HealthBanner";
import { useCreateJobFromUrl, useCreateJobFromUpload } from "@/lib/api/jobCreationQueries";
import { useState } from "react";
import type { ApiErrorEnvelope } from "@/lib/api/apiClient";
import { useTranslations } from "next-intl";

type TabType = "url" | "upload";

export default function IngestPage() {
    const t = useTranslations("Ingest");
    const [activeTab, setActiveTab] = useState<TabType>("url");

    return (
        <div className="mx-auto max-w-3xl space-y-8 p-6 sm:p-10">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold tracking-tight text-stone-900">
                    {t("title")}
                </h1>
                <p className="text-lg text-stone-600">
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
                        className={`flex-1 py-4 text-sm font-medium transition-all ${activeTab === "url"
                            ? "border-b-2 border-stone-800 bg-white text-stone-900 shadow-sm"
                            : "text-stone-500 hover:bg-stone-100 hover:text-stone-700"
                            }`}
                    >
                        {t("tabUrl")}
                    </button>
                    <button
                        onClick={() => setActiveTab("upload")}
                        className={`flex-1 py-4 text-sm font-medium transition-all ${activeTab === "upload"
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

function UrlForm() {
    const t = useTranslations("Ingest.urlForm");
    const [sourceUrl, setSourceUrl] = useState("");
    const [title, setTitle] = useState("");
    const [outputLanguage, setOutputLanguage] = useState("zh-Hans");
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
        <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
                <label htmlFor="url" className="block text-sm font-medium text-stone-700">
                    {t("labelUrl")} <span className="text-red-500">*</span>
                </label>
                <input
                    type="text"
                    id="url"
                    value={sourceUrl}
                    onChange={(e) => setSourceUrl(e.target.value)}
                    placeholder={t("placeholderUrl") || "https://..."}
                    className="block w-full rounded-lg border border-stone-200 bg-white px-4 py-3 text-stone-900 placeholder-stone-400 focus:border-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-200"
                />
                {sourceUrl && !isValidUrl(sourceUrl) && (
                    <p className="text-sm text-red-500">
                        {t("invalidUrl")}
                    </p>
                )}
            </div>

            <div className="space-y-2">
                <label htmlFor="title" className="block text-sm font-medium text-stone-700">
                    {t("labelTitle")}
                </label>
                <input
                    type="text"
                    id="title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder={t("placeholderTitle")}
                    className="block w-full rounded-lg border border-stone-200 bg-white px-4 py-3 text-stone-900 placeholder-stone-400 focus:border-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-200"
                />
            </div>

            <div className="space-y-2">
                <label htmlFor="outputLanguage" className="block text-sm font-medium text-stone-700">
                    {t("labelLang")}
                </label>
                <select
                    id="outputLanguage"
                    value={outputLanguage}
                    onChange={(e) => setOutputLanguage(e.target.value)}
                    className="block w-full rounded-lg border border-stone-200 bg-white px-4 py-3 text-stone-900 focus:border-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-200"
                >
                    <option value="zh-Hans">{t("options.zhHans")}</option>
                    <option value="en">{t("options.en")}</option>
                    <option value="auto">{t("options.auto")}</option>
                </select>
                <p className="text-sm text-stone-500">
                    {t("langDesc")}
                </p>
            </div>

            {errorMessage && (
                <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">
                    {errorMessage}
                </div>
            )}

            <button
                type="submit"
                disabled={!canSubmit || mutation.isPending}
                className="w-full rounded-lg bg-stone-800 px-4 py-3 text-base font-medium text-white transition-all hover:bg-stone-900 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-stone-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
                {mutation.isPending ? t("submitting") : t("submit")}
            </button>
        </form>
    );
}

function UploadForm() {
    const t = useTranslations("Ingest.uploadForm");
    const tUrl = useTranslations("Ingest.urlForm"); // Reuse generic translations if needed

    // Explicitly reusing options from urlForm
    const tOptions = useTranslations("Ingest.urlForm.options");

    const [file, setFile] = useState<File | null>(null);
    const [title, setTitle] = useState("");
    const [outputLanguage, setOutputLanguage] = useState("zh-Hans");
    const mutation = useCreateJobFromUpload();

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        if (selectedFile) {
            // Check if it's a video file
            if (!selectedFile.type.startsWith("video/")) {
                alert(t("selectFileError"));
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
            outputLanguage: outputLanguage.trim() || undefined,
        });
    };

    const errorMessage = mutation.error
        ? getErrorMessage(mutation.error)
        : null;

    return (
        <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
                <label htmlFor="file" className="block text-sm font-medium text-stone-700">
                    {t("labelFile")} <span className="text-red-500">*</span>
                </label>
                <div className="mt-2 rounded-lg border-2 border-dashed border-stone-200 bg-stone-50 px-6 py-10 transition-colors hover:bg-stone-100">
                    <input
                        type="file"
                        id="file"
                        accept="video/*"
                        onChange={handleFileChange}
                        className="block w-full text-sm text-stone-500 file:mr-4 file:rounded-full file:border-0 file:bg-stone-800 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-stone-700"
                    />
                    {file && (
                        <p className="mt-4 text-sm font-medium text-stone-600">
                            已选择: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
                        </p>
                    )}
                </div>
            </div>

            <div className="space-y-2">
                <label htmlFor="upload-title" className="block text-sm font-medium text-stone-700">
                    {tUrl("labelTitle")}
                </label>
                <input
                    type="text"
                    id="upload-title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder={tUrl("placeholderTitle")}
                    className="block w-full rounded-lg border border-stone-200 bg-white px-4 py-3 text-stone-900 placeholder-stone-400 focus:border-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-200"
                />
            </div>

            <div className="space-y-2">
                <label htmlFor="upload-outputLanguage" className="block text-sm font-medium text-stone-700">
                    {tUrl("labelLang")}
                </label>
                <select
                    id="upload-outputLanguage"
                    value={outputLanguage}
                    onChange={(e) => setOutputLanguage(e.target.value)}
                    className="block w-full rounded-lg border border-stone-200 bg-white px-4 py-3 text-stone-900 focus:border-stone-500 focus:outline-none focus:ring-2 focus:ring-stone-200"
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
                className="w-full rounded-lg bg-stone-800 px-4 py-3 text-base font-medium text-white transition-all hover:bg-stone-900 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-stone-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
                {mutation.isPending ? t("submitting") : t("submit")}
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
