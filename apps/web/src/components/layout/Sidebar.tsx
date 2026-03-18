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
            className={`flex flex-col border-r border-stone-200 bg-cream transition-all duration-300 ease-in-out ${isCollapsed ? "w-20 xl:w-24" : "w-64 xl:w-72"
                } h-screen sticky top-0`}
        >
            {/* Header / Brand */}
            <div className="flex h-20 xl:h-24 items-center justify-center border-b border-stone-100">
                <Link href="/" className="flex items-center gap-3 xl:gap-4 overflow-hidden px-4 xl:px-6">
                    <div className="flex h-10 w-10 xl:h-12 xl:w-12 min-w-[2.5rem] xl:min-w-[3rem] items-center justify-center rounded-xl xl:rounded-xl bg-stone-800 text-white shadow-md">
                        {/* Logo Icon Placeholder */}
                        <LayoutDashboard className="w-5 h-5 xl:w-6 xl:h-6" />
                    </div>
                    {!isCollapsed && (
                        <span className="font-bold text-lg xl:text-2xl tracking-tight text-stone-900 whitespace-nowrap opacity-100 transition-opacity duration-300">
                            {tSidebar("brand")}
                        </span>
                    )}
                </Link>
            </div>

            {/* Main Navigation */}
            <nav className="flex-1 space-y-2 p-4 xl:p-5 xl:space-y-3">
                {navItems.map((item) => {
                    const active = isActive(item.href);
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`flex items-center gap-3 xl:gap-4 rounded-lg xl:rounded-xl px-3 py-3 xl:px-4 xl:py-4 transition-colors ${active
                                ? "bg-stone-200 text-stone-900"
                                : "text-stone-500 hover:bg-stone-100 hover:text-stone-900"
                                }`}
                            title={isCollapsed ? item.name : undefined}
                        >
                            <item.icon className={`w-6 h-6 xl:w-7 xl:h-7 ${active ? "text-stone-900" : "text-stone-500"}`} />
                            {!isCollapsed && (
                                <span className="font-medium xl:text-lg whitespace-nowrap overflow-hidden">
                                    {item.name}
                                </span>
                            )}
                        </Link>
                    );
                })}
            </nav>

            {/* Bottom Actions */}
            <div className="border-t border-stone-100 p-4 xl:p-5 space-y-2 xl:space-y-3">
                {bottomItems.map((item) => {
                    const active = isActive(item.href);
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`flex items-center gap-3 xl:gap-4 rounded-lg xl:rounded-xl px-3 py-3 xl:px-4 xl:py-4 transition-colors ${active
                                ? "bg-stone-200 text-stone-900"
                                : "text-stone-500 hover:bg-stone-100 hover:text-stone-900"
                                }`}
                            title={isCollapsed ? item.name : undefined}
                        >
                            <item.icon className={`w-6 h-6 xl:w-7 xl:h-7 ${active ? "text-stone-900" : "text-stone-500"}`} />
                            {!isCollapsed && (
                                <span className="font-medium xl:text-lg whitespace-nowrap overflow-hidden">
                                    {item.name}
                                </span>
                            )}
                        </Link>
                    );
                })}

                <div className="flex items-center gap-3 xl:gap-4 rounded-lg xl:rounded-xl overflow-hidden">
                    <LanguageSwitcher isCollapsed={isCollapsed} />
                </div>

                {/* Collapse Toggle */}
                <button
                    onClick={toggleSidebar}
                    className="flex w-full items-center gap-3 xl:gap-4 rounded-lg xl:rounded-xl px-3 py-3 xl:px-4 xl:py-4 text-stone-400 hover:bg-stone-100 hover:text-stone-600 transition-colors"
                    title={isCollapsed ? tSidebar("collapse") : undefined}
                >
                    {isCollapsed ? <ChevronRight className="w-6 h-6 xl:w-7 xl:h-7" /> : <ChevronLeft className="w-6 h-6 xl:w-7 xl:h-7" />}
                    {!isCollapsed && (
                        <span className="font-medium xl:text-lg whitespace-nowrap overflow-hidden">
                            {tSidebar("collapse")}
                        </span>
                    )}
                </button>
            </div>
        </aside>
    );
}
