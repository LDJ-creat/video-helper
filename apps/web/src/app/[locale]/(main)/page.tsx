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
                <div className="flex flex-col items-center text-center w-full max-w-[1800px] space-y-8 2xl:space-y-12 animate-in fade-in slide-in-from-bottom-10 duration-1000">

                    {/* Badge */}
                    <div className="inline-flex items-center gap-2 rounded-full border border-stone-200 bg-white/80 px-4 py-1.5 2xl:px-6 2xl:py-2.5 text-xs 2xl:text-base font-semibold text-stone-600 shadow-sm backdrop-blur-md">
                        <Sparkles className="w-3.5 h-3.5 2xl:w-5 2xl:h-5 text-stone-800" />
                        <span>{t('title')}</span>
                    </div>

                    {/* Main Title */}
                    <h1 className="text-5xl font-extrabold tracking-tight text-stone-900 sm:text-6xl lg:text-7xl 2xl:text-8xl">
                        {t('title')}
                    </h1>

                    {/* Description */}
                    <p className="max-w-2xl 2xl:max-w-4xl text-lg 2xl:text-2xl leading-relaxed text-stone-500 sm:text-xl">
                        {t('description')}
                    </p>

                    {/* Primary CTA */}
                    <div className="pt-4 2xl:pt-8 w-full max-w-sm 2xl:max-w-md">
                        <Link
                            href="/ingest"
                            className="group relative flex h-14 2xl:h-20 items-center justify-center gap-3 overflow-hidden rounded-2xl 2xl:rounded-3xl bg-stone-900 px-10 text-lg 2xl:text-2xl font-bold text-white shadow-xl shadow-stone-200 transition-all hover:-translate-y-1 hover:bg-stone-800 active:scale-95"
                        >
                            <Video className="w-5 h-5 2xl:w-8 2xl:h-8" />
                            {t('cta')}
                            <ArrowRight className="w-5 h-5 2xl:w-8 2xl:h-8 transition-transform group-hover:translate-x-1" />

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
