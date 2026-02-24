"use client";

import Link from "next/link";
import { useTranslations } from 'next-intl';
import { RecentProjects } from "@/components/features/projects/RecentProjects";
import { Sparkles, Video, ArrowRight } from "lucide-react";

export default function Home() {
    const t = useTranslations('HomePage');

    return (
        <div className="relative flex min-h-full flex-col items-center justify-center font-sans text-stone-800 selection:bg-stone-200 selection:text-stone-900 overflow-hidden py-12">

            {/* Background Decorative Gradients */}
            <div className="absolute top-0 -z-10 h-full w-full bg-[#FDFBF7]">
                <div className="absolute top-[-10%] left-[-10%] h-[40%] w-[40%] rounded-full bg-orange-100/30 blur-[120px]" />
                <div className="absolute bottom-[-10%] right-[-10%] h-[40%] w-[40%] rounded-full bg-stone-200/30 blur-[120px]" />
            </div>

            <main className="relative z-10 flex w-full flex-col items-center px-6">

                {/* Hero Section */}
                <div className="flex flex-col items-center text-center max-w-4xl space-y-8 animate-in fade-in slide-in-from-bottom-10 duration-1000">

                    {/* Badge */}
                    <div className="inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white/80 px-4 py-1.5 text-xs font-semibold text-stone-600 shadow-sm backdrop-blur-md">
                        <Sparkles size={14} className="text-stone-800" />
                        <span>{t('title')}</span>
                    </div>

                    {/* Main Title */}
                    <h1 className="text-5xl font-extrabold tracking-tight text-stone-900 sm:text-6xl lg:text-7xl">
                        {t('title')}
                    </h1>

                    {/* Description */}
                    <p className="max-w-2xl text-lg leading-relaxed text-stone-500 sm:text-xl">
                        {t('description')}
                    </p>

                    {/* Primary CTA */}
                    <div className="pt-4">
                        <Link
                            href="/ingest"
                            className="group relative flex h-14 items-center justify-center gap-3 overflow-hidden rounded-2xl bg-stone-900 px-10 text-lg font-bold text-white shadow-xl shadow-stone-200 transition-all hover:-translate-y-1 hover:bg-stone-800 active:scale-95"
                        >
                            <Video size={20} />
                            {t('cta')}
                            <ArrowRight size={20} className="transition-transform group-hover:translate-x-1" />

                            {/* Shine Effect */}
                            <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/10 to-transparent transition-transform duration-1000 group-hover:translate-x-full" />
                        </Link>
                    </div>
                </div>

                {/* Recent Projects Preview */}
                <RecentProjects />
            </main>

            {/* Footer */}
            <footer className="mt-20 px-6 py-8 text-center text-xs font-medium tracking-tight text-stone-400">
                {t('footer')}
            </footer>
        </div>
    );
}
