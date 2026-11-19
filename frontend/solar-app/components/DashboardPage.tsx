"use client";

import { createContext, useContext, useLayoutEffect, type ReactNode } from "react";
import { usePathname } from "next/navigation";

export interface PageStatus {
    pathname: string;
    status: string;
    source?: string;
    updatedAt?: string;
}

export const PageStatusContext = createContext<(value: PageStatus) => void>(() => {});

export default function DashboardPage({
    children, status = "online", source, updatedAt,
}: Partial<Omit<PageStatus, "pathname">> & { children: ReactNode }) {
    const pathname = usePathname();
    const publish = useContext(PageStatusContext);
    useLayoutEffect(() => {
        publish({ pathname, status, source, updatedAt });
    }, [publish, pathname, status, source, updatedAt]);
    return children;
}
