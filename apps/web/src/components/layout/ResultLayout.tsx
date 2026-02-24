"use client";

import { useTranslations } from "next-intl";
import { ReactNode } from "react";

type ResultLayoutProps = {
    children: ReactNode;
    className?: string;
};

export function ResultLayout({ children, className = "" }: ResultLayoutProps) {
    const t = useTranslations("Results");

    return (
        <div className={`min-h-screen bg-[#FDFBF7] ${className}`}>
            {/* Header */}
            <header className="bg-white border-b border-stone-200 px-6 py-4">
                <div className="max-w-screen-2xl mx-auto flex items-center justify-between">
                    <h1 className="text-2xl font-bold tracking-tight text-stone-900">
                        {t("pageTitle")}
                    </h1>
                    {/* <div className="flex items-center gap-3">
                        <button className="px-4 py-2 text-sm font-medium text-stone-700 bg-stone-100 hover:bg-stone-200 rounded-lg transition-colors">
                            {t("export")}
                        </button>
                        <button className="px-4 py-2 text-sm font-medium text-white bg-stone-800 hover:bg-stone-900 rounded-lg transition-colors">
                            {t("settings")}
                        </button>
                    </div> */}
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-screen-2xl mx-auto px-6 py-6">
                {children}
            </main>
        </div>
    );
}
