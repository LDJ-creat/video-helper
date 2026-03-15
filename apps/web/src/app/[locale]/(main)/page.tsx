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
                <div className="flex flex-col items-center text-center w-full max-w-[1400px] space-y-8 xl:space-y-10 animate-in fade-in slide-in-from-bottom-10 duration-1000">

                    {/* Badge */}
                    <div className="inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white/80 px-4 py-1.5 xl:px-5 xl:py-2 text-xs xl:text-sm font-semibold text-stone-600 shadow-sm backdrop-blur-md">
                        <Sparkles className="w-3.5 h-3.5 xl:w-4 xl:h-4 text-stone-800" />
                        <span>{t('title')}</span>
                    </div>

                    {/* Main Title */}
                    <h1 className="text-5xl font-extrabold tracking-tight text-stone-900 sm:text-6xl xl:text-7xl">
                        {t('title')}
                    </h1>

                    {/* Description */}
                    <p className="max-w-2xl xl:max-w-3xl text-lg xl:text-xl leading-relaxed text-stone-500">
                        {t('description')}
                    </p>

                    {/* Primary CTA */}
                    <div className="pt-4 xl:pt-6 w-full max-w-sm xl:max-w-md">
                        <Link
                            href="/ingest"
                            className="group relative flex h-14 xl:h-16 items-center justify-center gap-3 overflow-hidden rounded-2xl xl:rounded-2xl bg-stone-900 px-10 text-lg xl:text-xl font-bold text-white shadow-xl shadow-stone-200 transition-all hover:-translate-y-1 hover:bg-stone-800 active:scale-95"
                        >
                            <Video className="w-5 h-5 xl:w-6 xl:h-6" />
                            {t('cta')}
                            <ArrowRight className="w-5 h-5 xl:w-6 xl:h-6 transition-transform group-hover:translate-x-1" />

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
