"use client";

import { useProjects } from "@/lib/api/projectQueries";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Clock, ArrowRight, PlayCircle } from "lucide-react";

export function RecentProjects() {
    const t = useTranslations("HomePage");
    const tProj = useTranslations("Projects");
    const { data, isLoading } = useProjects();

    const projects = data?.pages?.[0]?.items?.slice(0, 3) ?? [];

    if (isLoading) {
        return (
            <div className="w-full max-w-4xl mx-auto mt-12 space-y-4">
                <div className="h-6 w-32 bg-stone-200 animate-pulse rounded" />
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[1, 2, 3].map((i) => (
                        <div key={i} className="h-32 bg-stone-100 animate-pulse rounded-xl" />
                    ))}
                </div>
            </div>
        );
    }

    if (projects.length === 0) return null;

    return (
        <div className="w-full max-w-5xl mx-auto mt-16 px-6 animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-300">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-semibold text-stone-800 flex items-center gap-2">
                    <Clock size={20} className="text-stone-400" />
                    {t("recentTitle")}
                </h2>
                <Link
                    href="/projects"
                    className="text-sm font-medium text-stone-500 hover:text-stone-900 transition-colors flex items-center gap-1 group"
                >
                    {t("viewAll")}
                    <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
                </Link>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {projects.map((project) => (
                    <Link
                        key={project.projectId}
                        href={`/projects/${project.projectId}/results`}
                        className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-stone-200 bg-white/50 p-5 backdrop-blur-sm transition-all hover:border-stone-300 hover:bg-white hover:shadow-xl hover:shadow-stone-200/50 active:scale-[0.98]"
                    >
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${project.sourceType === 'youtube' ? 'bg-red-50 text-red-600' :
                                        project.sourceType === 'bilibili' ? 'bg-pink-50 text-pink-600' :
                                            'bg-blue-50 text-blue-600'
                                    }`}>
                                    {project.sourceType}
                                </span>
                                <PlayCircle size={16} className="text-stone-300 group-hover:text-stone-900 transition-colors" />
                            </div>
                            <h3 className="text-sm font-semibold text-stone-900 line-clamp-2 leading-snug group-hover:text-stone-800">
                                {project.title || tProj("untitled")}
                            </h3>
                        </div>
                        <div className="mt-4 pt-3 border-t border-stone-100 flex items-center justify-between">
                            <span className="text-[10px] text-stone-400 font-medium">
                                {new Date(project.updatedAtMs).toLocaleDateString()}
                            </span>
                            <span className="text-[10px] font-bold text-stone-900 opacity-0 group-hover:opacity-100 transition-opacity">
                                OPEN →
                            </span>
                        </div>
                    </Link>
                ))}
            </div>
        </div>
    );
}
