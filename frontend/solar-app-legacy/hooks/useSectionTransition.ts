"use client";

import { useLayoutEffect, useRef } from "react";
import { useRouter } from "next/navigation";

type PendingTransition = {
    href: string;
    commit: () => void;
    cancel: () => void;
};

export function useSectionTransition(pathname: string, items: readonly { href: string }[]) {
    const router = useRouter();
    const mainRef = useRef<HTMLElement>(null);
    const pending = useRef<PendingTransition | null>(null);
    const section = (path: string) => items.findIndex(({ href }) =>
        path === href || (href !== "/" && path.startsWith(href + "/")));
    const index = section(pathname);
    const previous = useRef(index);

    useLayoutEffect(() => {
        const direction = Math.sign(index - previous.current);
        previous.current = index;
        const active = pending.current;
        if (active) {
            // An older router push may commit while a newer tab is taking its snapshot.
            if (active.href === pathname) active.commit();
            return;
        }
        if (!direction || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
        const animation = mainRef.current?.animate([
            { transform: `translateX(${direction * 28}px)`, opacity: 0 },
            { transform: "none", opacity: 1 },
        ], { duration: 260, easing: "cubic-bezier(.22,.61,.36,1)" });
        return () => animation?.cancel();
    }, [index, pathname]);

    useLayoutEffect(() => {
        const cancel = () => pending.current?.cancel();
        window.addEventListener("popstate", cancel);
        return () => {
            window.removeEventListener("popstate", cancel);
            cancel();
        };
    }, []);

    function navigate(event: { preventDefault(): void }, href: string) {
        pending.current?.cancel();
        if (section(href) === index || !document.startViewTransition ||
            matchMedia("(prefers-reduced-motion: reduce)").matches) return;
        event.preventDefault();
        const root = document.documentElement;
        root.dataset.sectionSlide = section(href) > index ? "forward" : "back";
        let commit!: () => void;
        const committed = new Promise<void>(resolve => { commit = resolve; });
        const transition = document.startViewTransition(async () => {
            if (pending.current !== entry) return;
            router.push(href);
            // Release the snapshot if a cold route takes time to arrive.
            const timer = window.setTimeout(entry.cancel, 180);
            await committed;
            window.clearTimeout(timer);
        });
        function clear() {
            if (pending.current === entry) {
                pending.current = null;
                delete root.dataset.sectionSlide;
            }
        }
        const entry = { href, commit, cancel() {
            transition.skipTransition();
            commit();
            clear();
        } };
        pending.current = entry;
        void transition.finished.then(clear, clear);
    }

    return { mainRef, navigate };
}
