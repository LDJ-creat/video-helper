"use client";

import { useProjects } from "@/lib/api/projectQueries";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Clock, ArrowRight, PlayCircle } from "lucide-react";

export function RecentProjects() {
    const t = useTranslations("HomePage");
    const tProj = useTranslations("Projects");
    const { data, isLoading } = useProjects();

    const projects = data?.pages?.[0]?.items?.slice(0, 4) ?? [];

    if (isLoading) {
        return (
            <div className="w-full max-w-[1800px] mx-auto mt-12 2xl:mt-24 space-y-4">
                <div className="h-6 w-32 bg-stone-200 animate-pulse rounded" />
                <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-4 gap-4 2xl:gap-8">
                    {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="h-32 2xl:h-48 bg-stone-100 animate-pulse rounded-xl" />
                    ))}
                </div>
            </div>
        );
    }

    if (projects.length === 0) return null;

    return (
        <div className="w-full max-w-[1800px] mx-auto mt-16 2xl:mt-32 px-6 animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-300">
            <div className="flex items-center justify-between mb-6 2xl:mb-10">
                <h2 className="text-xl 2xl:text-3xl font-semibold text-stone-800 flex items-center gap-2">
                    <Clock className="text-stone-400 w-5 h-5 2xl:w-8 2xl:h-8" />
                    {t("recentTitle")}
                </h2>
                <Link
                    href="/projects"
                    className="text-sm 2xl:text-xl font-medium text-stone-500 hover:text-stone-900 transition-colors flex items-center gap-1 group"
                >
                    {t("viewAll")}
                    <ArrowRight className="w-3.5 h-3.5 2xl:w-6 2xl:h-6 group-hover:translate-x-1 transition-transform" />
                </Link>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-4 gap-6 2xl:gap-10">
                {projects.map((project) => (
                    <Link
                        key={project.projectId}
                        href={`/projects/${project.projectId}/results`}
                        className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-stone-200 bg-white/50 p-5 2xl:p-8 backdrop-blur-sm transition-all hover:border-stone-300 hover:bg-white hover:shadow-xl hover:shadow-stone-200/50 active:scale-[0.98]"
                    >
                        <div className="space-y-3 2xl:space-y-5">
                            <div className="flex items-center justify-between">
                                <span className={`text-[10px] 2xl:text-sm font-bold uppercase tracking-wider px-2 py-0.5 2xl:px-3 rounded-full ${project.sourceType === 'youtube' ? 'bg-red-50 text-red-600' :
                                    project.sourceType === 'bilibili' ? 'bg-pink-50 text-pink-600' :
                                        'bg-blue-50 text-blue-600'
                                    }`}>
                                    {project.sourceType}
                                </span>
                                <PlayCircle className="text-stone-300 group-hover:text-stone-900 transition-colors w-4 h-4 2xl:w-7 2xl:h-7" />
                            </div>
                            <h3 className="text-sm 2xl:text-xl font-semibold text-stone-900 line-clamp-2 leading-snug group-hover:text-stone-800">
                                {project.title || tProj("untitled")}
                            </h3>
                        </div>
                        <div className="mt-4 pt-3 2xl:mt-6 2xl:pt-4 border-t border-stone-100 flex items-center justify-between">
                            <span className="text-[10px] 2xl:text-sm text-stone-400 font-medium">
                                {new Date(project.updatedAtMs).toLocaleDateString()}
                            </span>
                            <span className="text-[10px] 2xl:text-sm font-bold text-stone-900 opacity-0 group-hover:opacity-100 transition-opacity">
                                OPEN →
                            </span>
                        </div>
                    </Link>
                ))}
            </div>
        </div>
    );
}
