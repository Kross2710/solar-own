"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import SettingsSheet from "@/components/settings/SettingsSheet";
import { useNotices } from "@/hooks/useAssistant";

interface DashboardShellProps {
    children: ReactNode;
    status?: string;
    source?: string;
}

export default function DashboardShell({
    children,
    status = "online",
    source = "MOCK",
}: DashboardShellProps) {
    const pathname = usePathname();
    const [settingsOpen, setSettingsOpen] = useState(false);
    const { data: noticeData } = useNotices();
    // Only warnings earn a dot; info notices wait quietly on the Assistant tab.
    const hasWarning = (noticeData?.notices ?? []).some((notice) => notice.severity === "warn");

    const navClass = (href: string) =>
        `nav-btn ${pathname === href ? "active" : ""}`;

    let title: ReactNode = "solar.home";
    if (pathname === "/") {
        title = (
            <>
                solar<span className="text-zinc-500">.home</span>
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

    return (
        <div className="min-h-screen w-full bg-[#04060c] text-[#eef1f8]">
            <div className="aurora" aria-hidden="true" />

            <div className="app">
                <header className="topbar">
                    <h1 className="text-sm font-bold">
                        {title}
                    </h1>

                    <div className="meta">
                        <span className="status">
                            <span
                                className={`dot ${status === "error" ? "dot--off" : "dot--on"
                                    }`}
                            />
                            {status}
                        </span>

                        {source && <span className="badge">{source}</span>}

                        <button
                            className="gear"
                            type="button"
                            aria-label="Settings"
                            aria-haspopup="dialog"
                            onClick={() => setSettingsOpen(true)}
                        >
                            <i className="fa-solid fa-gear" />
                        </button>
                    </div>
                </header>

                <nav className="nav" aria-label="Sections">
                    <Link href="/" className={navClass("/")}>
                        <span className="nav-ico">
                            <i className="fa-solid fa-house" />
                        </span>
                        <span className="nav-lbl">Overview</span>
                    </Link>

                    <Link href="/history" className={navClass("/history")}>
                        <span className="nav-ico">
                            <i className="fa-solid fa-chart-column" />
                        </span>
                        <span className="nav-lbl">History</span>
                    </Link>

                    <Link href="/money" className={navClass("/money")}>
                        <span className="nav-ico">
                            <i className="fa-solid fa-coins" />
                        </span>
                        <span className="nav-lbl">Money</span>
                    </Link>

                    <Link href="/optimization" className={navClass("/optimization")}>
                        <span className="nav-ico">
                            <i className="fa-solid fa-lightbulb" />
                        </span>
                        <span className="nav-lbl">Optimization</span>
                    </Link>

                    <Link href="/assistant" className={navClass("/assistant")}>
                        <span className="nav-ico">
                            <i className="fa-solid fa-robot" />
                            {hasWarning && <span className="nav-dot" aria-label="New warning" />}
                        </span>
                        <span className="nav-lbl">Assistant</span>
                    </Link>
                </nav>

                <main className="flex flex-col gap-7">{children}</main>
            </div>

            <SettingsSheet open={settingsOpen} onClose={() => setSettingsOpen(false)} />
        </div>
    );
}