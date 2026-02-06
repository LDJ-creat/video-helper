"use client";

import { Sidebar } from "@/components/layout/Sidebar";

export default function MainLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="flex min-h-screen bg-stone-50">
            <Sidebar />
            <div className="flex-1">
                {children}
            </div>
        </div>
    );
}
