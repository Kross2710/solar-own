"use client";

import {useLayoutEffect, useRef} from "react";
import {useRouter} from "next/navigation";

const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

export function useSectionTransition(pathname, pages) {
  const router = useRouter();
  const pending = useRef(null);
  const index = pages.findIndex(([path]) => path === pathname);
  const previous = useRef(index);

  useLayoutEffect(() => {
    const from = previous.current;
    previous.current = index;
    const active = pending.current;
    if (active) {
      if (active.path === pathname) active.commit();
      return;
    }
    if (from < 0 || index < 0 || index === from || reducedMotion()) return;
    const offset = Math.sign(index - from) * 28;
    const animation = document.querySelector("main")?.animate([
      {transform: `translateX(${offset}px)`, opacity: 0},
      {transform: "none", opacity: 1},
    ], {duration: 260, easing: "cubic-bezier(.22,.61,.36,1)"});
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

  return function navigate(event, target, suffix) {
    pending.current?.cancel();
    const next = pages.findIndex(([path]) => path === target);
    if (index < 0 || next < 0 || index === next || !document.startViewTransition || reducedMotion()) return;
    event.preventDefault();
    const root = document.documentElement;
    root.dataset.sectionSlide = next > index ? "forward" : "back";
    let commit;
    const committed = new Promise(resolve => { commit = resolve; });
    const transition = document.startViewTransition(async () => {
      if (pending.current !== entry) return;
      router.push(target + suffix);
      // Let a cold route finish with the entry animation instead of freezing the old view.
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
    const entry = {path: target, commit, cancel() {
      transition.skipTransition();
      commit();
      clear();
    }};
    pending.current = entry;
    // Skipping a snapshot rejects ready even when the route update finishes normally.
    void transition.ready.catch(() => {});
    void transition.finished.then(clear, clear);
  };
}
