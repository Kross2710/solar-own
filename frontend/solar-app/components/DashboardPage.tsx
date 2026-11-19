"use client";

import { createContext, useContext, useEffect, useState, useLayoutEffect, type ReactNode } from "react";
import { usePathname } from "next/navigation";

export interface PageStatus {
    pathname: string;
    status: string;
    source?: string;
    updatedAt?: string;
}

export const PageStatusContext = createContext<(value: PageStatus) => void>(() => {});

export default function DashboardPage({
    children, status = "online", source, updatedAt, refreshing = false,
}: Partial<Omit<PageStatus, "pathname">> & { children: ReactNode; refreshing?: boolean }) {
    const pathname = usePathname();
    const publish = useContext(PageStatusContext);
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
    let visibleStatus = status;
    if (status === "connecting" && !slow) visibleStatus = "";
    if (refreshing && slow && (status === "online" || status === "live")) visibleStatus = "updating";
    useLayoutEffect(() => {
        publish({ pathname, status: visibleStatus, source, updatedAt });
    }, [publish, pathname, visibleStatus, source, updatedAt]);
    return children;
}

export function PageUnavailable({ failed = false }: { failed?: boolean }) {
    return (
        <DashboardPage status={failed ? "error" : "connecting"}>
            <div className="rounded-[22px] border border-white/10 bg-card/90 p-6 text-muted"
                role={failed ? "alert" : "status"}>
                {failed ? "Couldn’t load data from the backend." : (
                    <><span aria-hidden="true">—</span><span className="sr-only">Loading dashboard data</span></>
                )}
            </div>
        </DashboardPage>
    );
}
