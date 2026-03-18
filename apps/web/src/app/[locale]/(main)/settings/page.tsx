"use client";

import { useTranslations } from "next-intl";
import { SettingsForm } from "@/components/features/settings/SettingsForm";

export default function SettingsPage() {
    const t = useTranslations("Settings");

    return (
        <main className="p-6 sm:p-10 xl:p-12 max-w-3xl xl:max-w-5xl mx-auto space-y-8 xl:space-y-10">
            <h1 className="text-2xl md:text-3xl xl:text-4xl font-bold mb-6 xl:mb-8">{t("title")}</h1>

            <div className="mb-8 xl:mb-12">
                <h2 className="text-lg md:text-xl xl:text-2xl font-semibold mb-3 xl:mb-4">{t("modelConfig")}</h2>
                <p className="text-sm xl:text-base text-stone-600 mb-6 xl:mb-8">
                    {t("modelConfigDesc")}
                </p>
                <SettingsForm />
            </div>
        </main>
    );
}
