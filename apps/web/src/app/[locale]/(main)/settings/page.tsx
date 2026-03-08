"use client";

import { useTranslations } from "next-intl";
import { SettingsForm } from "@/components/features/settings/SettingsForm";

export default function SettingsPage() {
    const t = useTranslations("Settings");

    return (
        <main className="p-6 sm:p-10 2xl:p-16 max-w-5xl 2xl:max-w-7xl mx-auto space-y-8 2xl:space-y-12">
            <h1 className="text-2xl 2xl:text-5xl font-bold mb-6 2xl:mb-10">{t("title")}</h1>

            <div className="mb-8 2xl:mb-16">
                <h2 className="text-lg 2xl:text-3xl font-semibold mb-4 2xl:mb-6">{t("modelConfig")}</h2>
                <p className="text-sm 2xl:text-xl text-stone-600 mb-6 2xl:mb-10">
                    {t("modelConfigDesc")}
                </p>
                <SettingsForm />
            </div>
        </main>
    );
}
