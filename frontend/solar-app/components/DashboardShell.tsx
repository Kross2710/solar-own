"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import UpdatedAgo from "@/components/overview/UpdatedAgo";
import SettingsSheet from "@/components/settings/SettingsSheet";
import { useNotices } from "@/hooks/useAssistant";

import { useSectionTransition } from "@/hooks/useSectionTransition";
import { PageStatusContext, type PageStatus } from "./DashboardPage";

const NAV_ITEMS = [
    { href: "/", label: "Overview", icon: "fa-house" },
    { href: "/history", label: "History", icon: "fa-chart-column" },
    { href: "/money", label: "Money", icon: "fa-coins" },
    { href: "/optimization", label: "Optimization", icon: "fa-lightbulb" },
    { href: "/assistant", label: "Assistant", icon: "fa-robot" },
];

const pillClass =
    "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-white/10 bg-white/5 px-3 py-[5px] text-[11px] font-semibold text-muted";

const DOT_CLASS: Record<string, string> = {
    online: "bg-good text-good/60 animate-[status-blink_2s_infinite]",
    error: "bg-grid-in text-grid-in/55 animate-[status-blink_1.3s_infinite]",
    connecting: "bg-pv text-pv/50 animate-[status-blink_2.4s_infinite]",
};

export default function DashboardShell({ children }: { children: ReactNode }) {
    const pathname = usePathname();
    const { mainRef, navigate } = useSectionTransition(pathname, NAV_ITEMS);
    const [pageStatus, setPageStatus] = useState<PageStatus>();
    const activeStatus = pageStatus?.pathname === pathname ? pageStatus : undefined;
    const { status, source, updatedAt } = activeStatus ?? {};
    const [settingsOpen, setSettingsOpen] = useState(false);
    const { data: noticeData } = useNotices();
    // Only warnings earn a dot; info notices wait quietly on the Assistant tab.
    const hasWarning = (noticeData?.notices ?? []).some((notice) => notice.severity === "warn");

    let title: ReactNode = "solar.home";
    if (pathname === "/") {
        title = (
            <>
                <span className="lg:hidden">
                    solar<span className="text-zinc-500">.home</span>
                </span>
                <span className="hidden lg:inline">Overview</span>
            </>
        );
    } else if (pathname.startsWith("/history")) {
        title = "History";
    } else if (pathname.startsWith("/money")) {
        title = "Money";
    } else if (pathname.startsWith("/optimization")) {
        title = "Optimization";
    } else if (pathname.startsWith("/assistant")) {
        title = "Assistant";
    }

    const statusPill = status && (
        <span className={pillClass}>
            <span className={`inline-block size-1.5 rounded-full shadow-[0_0_6px_currentColor] motion-reduce:animate-none ${DOT_CLASS[status] ?? DOT_CLASS.online}`} />
            {status}
        </span>
    );
    const settingsButton = (
        <button
            className="inline-flex size-[30px] shrink-0 cursor-pointer items-center justify-center rounded-full text-[15px] text-dim transition-colors duration-200 hover:text-fg"
            type="button"
            aria-label="Settings"
            aria-haspopup="dialog"
            onClick={() => setSettingsOpen(true)}
        >
            <i className="fa-solid fa-gear" />
        </button>
    );

    return (
        <div className="min-h-screen w-full bg-ink text-fg lg:pl-[220px]">
            <div className="aurora" aria-hidden="true" />

            {/* Desktop: navigation and connection status live in a fixed sidebar. */}
            <aside className="fixed inset-y-0 left-0 z-40 hidden w-[220px] flex-col border-r border-white/[0.06] bg-ink/60 px-4 py-7 backdrop-blur-xl lg:flex">
                <p className="px-3 text-sm font-bold">
                    solar<span className="text-zinc-500">.home</span>
                </p>
                <nav className="mt-8 flex flex-col gap-1" aria-label="Sections">
                    {NAV_ITEMS.map(({ href, label, icon }) => {
                        const active = pathname === href || (href !== "/" && pathname.startsWith(href + "/"));
                        return (
                            <Link
                                key={href}
                                href={href}
                                onNavigate={event => navigate(event, href)}
                                aria-current={active ? "page" : undefined}
                                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] transition-colors duration-200 ${active ? "bg-white/10 font-bold text-fg" : "font-semibold text-dim hover:bg-white/[0.04] hover:text-fg"}`}
                            >
                                <span className="relative w-4 text-center text-[14px]">
                                    <i className={`fa-solid ${icon}`} />
                                    {href === "/assistant" && hasWarning && (
                                        <span className="absolute -top-1 -right-1.5 size-[9px] rounded-full border-2 border-ink bg-grid-in" aria-label="New warning" />
                                    )}
                                </span>
                                {label}
                            </Link>
                        );
                    })}
                </nav>
                <div className="mt-auto flex flex-col gap-2 px-1 text-[12px] text-muted">
                    <div className="flex flex-wrap items-center gap-2">
                        {statusPill}
                        {source ? <span className={pillClass}>{source}</span> : null}
                    </div>
                    <div className="flex items-center justify-between pl-1">
                        <UpdatedAgo iso={updatedAt} />
                        {settingsButton}
                    </div>
                </div>
            </aside>

            {/* "app" is the zoom target for the large text modes in globals.css. */}
            <div className="app relative z-1 mx-auto flex max-w-[1080px] flex-col gap-7 px-7 pt-8 pb-14 max-sm:pb-[calc(96px+env(safe-area-inset-bottom,0px))] max-[480px]:gap-6 max-[480px]:px-5 max-[480px]:pt-6 max-[480px]:pb-[calc(88px+env(safe-area-inset-bottom,0px))] lg:max-w-[1240px] lg:px-10">
                <header className="flex flex-wrap items-center justify-between gap-3 max-[480px]:flex-nowrap">
                    <h1 className="text-sm font-bold lg:text-xl">
                        {title}
                    </h1>

                    <div className="flex items-center gap-2 text-[13px] text-muted max-sm:justify-end max-[480px]:shrink-0 max-[480px]:gap-1.5 max-[480px]:text-[11px] lg:hidden">
                        {statusPill}

                        <UpdatedAgo iso={updatedAt} />

                        {source ? <span className={`${pillClass} max-[480px]:hidden`}>{source}</span> : null}

                        {settingsButton}
                    </div>
                </header>

                <nav
                    className="sticky top-0 z-30 flex gap-0.5 py-2 backdrop-blur-[8px] max-sm:fixed max-sm:inset-x-0 max-sm:top-auto max-sm:bottom-0 max-sm:z-50 max-sm:bg-[linear-gradient(180deg,transparent,rgba(4,6,12,0.9)_34%)] max-sm:px-[18px] max-sm:pt-2.5 max-sm:pb-[calc(12px+env(safe-area-inset-bottom,0px))] max-sm:backdrop-blur-none lg:hidden"
                    aria-label="Sections"
                >
                    {NAV_ITEMS.map(({ href, label, icon }) => {
                        const active = pathname === href || (href !== "/" && pathname.startsWith(href + "/"));
                        return (
                            <Link
                                key={href}
                                href={href}
                                onNavigate={event => navigate(event, href)}
                                aria-current={active ? "page" : undefined}
                                className={`flex flex-1 flex-col items-center gap-1 px-1 py-1.5 text-[10.5px] whitespace-nowrap transition-colors duration-200 hover:text-fg ${active ? "font-bold text-fg" : "font-semibold text-dim"}`}
                            >
                                <span className={`relative flex size-[34px] items-center justify-center rounded-xl border text-[15px] leading-none transition-[background-color,border-color] duration-200 ${active ? "border-white/16 bg-white/10" : "border-transparent"}`}>
                                    <i className={`fa-solid ${icon}`} />
                                    {href === "/assistant" && hasWarning && (
                                        <span className="absolute -top-0.5 -right-0.5 size-[9px] rounded-full border-2 border-ink bg-grid-in" aria-label="New warning" />
                                    )}
                                </span>
                                {label}
                            </Link>
                        );
                    })}
                </nav>

                <main ref={mainRef} className="dashboard-content flex flex-col gap-7"><PageStatusContext.Provider value={setPageStatus}>{children}</PageStatusContext.Provider></main>
            </div>

            <SettingsSheet open={settingsOpen} onClose={() => setSettingsOpen(false)} />
        </div>
    );
}