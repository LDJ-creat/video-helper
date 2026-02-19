"use client";

import LanguageSwitcher from "@/components/LanguageSwitcher";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "@/i18n/navigation";
import { useState } from "react";
import {
    PlusCircle,
    FolderOpen,
    Settings,
    ChevronLeft,
    ChevronRight,
    LayoutDashboard
} from "lucide-react";

export function Sidebar() {
    const t = useTranslations("Navigation");
    const tSidebar = useTranslations("Sidebar");
    const pathname = usePathname();
    const [isCollapsed, setIsCollapsed] = useState(false);

    const toggleSidebar = () => setIsCollapsed(!isCollapsed);

    const navItems = [
        {
            name: t("ingest"),
            href: "/ingest",
            icon: PlusCircle,
        },
        {
            name: t("projects"),
            href: "/projects",
            icon: FolderOpen,
        },
    ];

    const bottomItems = [
        {
            name: t("settings"),
            href: "/settings",
            icon: Settings,
        },
    ];

    const isActive = (path: string) => pathname === path || pathname?.startsWith(`${path}/`);

    return (
        <aside
            className={`flex flex-col border-r border-stone-200 bg-cream transition-all duration-300 ease-in-out ${isCollapsed ? "w-20" : "w-64"
                } h-screen sticky top-0`}
        >
            {/* Header / Brand */}
            <div className="flex h-20 items-center justify-center border-b border-stone-100">
                <Link href="/" className="flex items-center gap-3 overflow-hidden px-4">
                    <div className="flex h-10 w-10 min-w-[2.5rem] items-center justify-center rounded-xl bg-stone-800 text-white shadow-md">
                        {/* Logo Icon Placeholder */}
                        <LayoutDashboard size={20} />
                    </div>
                    {!isCollapsed && (
                        <span className="font-bold text-lg tracking-tight text-stone-900 whitespace-nowrap opacity-100 transition-opacity duration-300">
                            {tSidebar("brand")}
                        </span>
                    )}
                </Link>
            </div>

            {/* Main Navigation */}
            <nav className="flex-1 space-y-2 p-4">
                {navItems.map((item) => {
                    const active = isActive(item.href);
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`flex items-center gap-3 rounded-lg px-3 py-3 transition-colors ${active
                                ? "bg-stone-200 text-stone-900"
                                : "text-stone-500 hover:bg-stone-100 hover:text-stone-900"
                                }`}
                            title={isCollapsed ? item.name : undefined}
                        >
                            <item.icon size={24} className={active ? "text-stone-900" : "text-stone-500"} />
                            {!isCollapsed && (
                                <span className="font-medium whitespace-nowrap overflow-hidden">
                                    {item.name}
                                </span>
                            )}
                        </Link>
                    );
                })}
            </nav>

            {/* Bottom Actions */}
            <div className="border-t border-stone-100 p-4 space-y-2">
                {bottomItems.map((item) => {
                    const active = isActive(item.href);
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`flex items-center gap-3 rounded-lg px-3 py-3 transition-colors ${active
                                ? "bg-stone-200 text-stone-900"
                                : "text-stone-500 hover:bg-stone-100 hover:text-stone-900"
                                }`}
                            title={isCollapsed ? item.name : undefined}
                        >
                            <item.icon size={24} className={active ? "text-stone-900" : "text-stone-500"} />
                            {!isCollapsed && (
                                <span className="font-medium whitespace-nowrap overflow-hidden">
                                    {item.name}
                                </span>
                            )}
                        </Link>
                    );
                })}

                <div className={`flex items-center gap-3 rounded-lg px-3 py-3 ${isCollapsed ? 'justify-center' : ''}`}>
                    <LanguageSwitcher />
                </div>

                {/* Collapse Toggle */}
                <button
                    onClick={toggleSidebar}
                    className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-stone-400 hover:bg-stone-100 hover:text-stone-600 transition-colors"
                    title={isCollapsed ? tSidebar("collapse") : undefined}
                >
                    {isCollapsed ? <ChevronRight size={24} /> : <ChevronLeft size={24} />}
                    {!isCollapsed && (
                        <span className="font-medium whitespace-nowrap overflow-hidden">
                            {tSidebar("collapse")}
                        </span>
                    )}
                </button>
            </div>
        </aside>
    );
}
