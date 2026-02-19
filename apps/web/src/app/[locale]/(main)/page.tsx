import Link from "next/link";
import { useTranslations } from 'next-intl';

export default function Home() {
    const t = useTranslations('Landing');
    const tNav = useTranslations('Navigation'); // For button labels

    return (
        <div className="flex h-full flex-col font-sans text-stone-800 selection:bg-orange-100 selection:text-orange-900">
            <main className="flex w-full flex-col items-center gap-12 px-6 py-20 text-center sm:items-start sm:text-left">

                {/* Header Section */}
                <div className="flex flex-col items-center gap-6 sm:items-start">
                    {/* Logo / Brand */}
                    <div className="text-sm font-bold tracking-widest uppercase text-stone-500">
                        {t('title')}
                    </div>

                    <h1 className="max-w-xl text-4xl font-bold tracking-tight text-stone-900 sm:text-5xl md:text-6xl">
                        {t('title')}
                    </h1>
                    <p className="max-w-lg text-lg leading-relaxed text-stone-600">
                        {t('description')}
                    </p>
                </div>

                {/* Action Buttons */}
                <div className="flex w-full flex-col gap-4 sm:w-auto sm:flex-row">
                    <Link
                        href="/ingest"
                        className="flex h-12 items-center justify-center rounded-lg bg-stone-800 px-8 text-base font-medium text-white shadow-sm transition-all hover:bg-stone-900 hover:shadow-md active:scale-95"
                    >
                        {tNav('ingest')}
                    </Link>
                    <Link
                        href="/projects"
                        className="flex h-12 items-center justify-center rounded-lg border border-stone-200 bg-white px-8 text-base font-medium text-stone-700 shadow-sm transition-all hover:border-stone-300 hover:bg-stone-50 active:scale-95"
                    >
                        {tNav('projects')}
                    </Link>
                    <Link
                        href="/settings"
                        className="flex h-12 items-center justify-center rounded-lg border border-transparent px-6 text-base font-medium text-stone-500 transition-all hover:bg-stone-100 hover:text-stone-700 active:scale-95"
                    >
                        {tNav('settings')}
                    </Link>
                </div>
            </main>

            {/* Footer / Decorative */}
            <footer className="mt-auto px-6 py-6 text-xs text-stone-400">
                {t('footer')}
            </footer>
        </div>
    );
}
