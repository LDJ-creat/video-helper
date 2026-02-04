"use client";

import { SettingsForm } from "@/components/features/SettingsForm";

export default function SettingsPage() {
    return (
        <main className="p-6 max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold mb-6">设置</h1>

            <div className="mb-8">
                <h2 className="text-lg font-semibold mb-4">模型配置</h2>
                <p className="text-sm text-gray-600 mb-6">
                    配置分析所使用的 AI 模型提供方和参数。修改后将立即生效。
                </p>
                <SettingsForm />
            </div>
        </main>
    );
}
