"use client";

import { useEffect, useState, type ReactNode } from "react";

export default function DashboardPage({
    children, status = "online", refreshing = false,
}: { children: ReactNode; status?: "online" | "connecting" | "error"; refreshing?: boolean }) {
    const pending = status === "connecting" || refreshing;
    const [slow, setSlow] = useState(false);
    useEffect(() => {
        if (!pending) return;
        const timer = setTimeout(() => setSlow(true), 2000);
        return () => {
            clearTimeout(timer);
            setSlow(false);
        };
    }, [pending]);
    let notice = "";
    if (status === "error") notice = "Couldn’t refresh all data on this page.";
    else if (pending && slow) notice = status === "connecting" ? "Connecting…" : "Updating…";
    return <>
        {children}
        {notice && <p role="status" className="text-xs text-muted">{notice}</p>}
    </>;
}

export function PageUnavailable({ failed = false }: { failed?: boolean }) {
    if (failed) return <p role="alert" className="text-sm text-grid-in">Couldn’t load data from the backend.</p>;
    return (
        <DashboardPage status="connecting">
            <div className="rounded-[22px] border border-white/10 bg-card/90 p-6 text-muted"
                role="status">
                <span aria-hidden="true">—</span><span className="sr-only">Loading dashboard data</span>
            </div>
        </DashboardPage>
    );
}
