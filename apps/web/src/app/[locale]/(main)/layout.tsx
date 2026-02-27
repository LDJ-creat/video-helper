"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { UpdateBanner } from "@/components/UpdateBanner";

export default function MainLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="flex min-h-screen bg-stone-50">
            <Sidebar />
            <div className="flex-1 overflow-y-auto no-scrollbar">
                <div className="px-6 pt-6">
                    <UpdateBanner />
                </div>
                {children}
            </div>
        </div>
    );
}
