"use client";

import { useTranslations } from "next-intl";
import { SettingsForm } from "@/components/features/SettingsForm";

export default function SettingsPage() {
    const t = useTranslations("Settings");

    return (
        <main className="p-6 max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold mb-6">{t("title")}</h1>

            <div className="mb-8">
                <h2 className="text-lg font-semibold mb-4">{t("modelConfig")}</h2>
                <p className="text-sm text-gray-600 mb-6">
                    {t("modelConfigDesc")}
                </p>
                <SettingsForm />
            </div>
        </main>
    );
}
