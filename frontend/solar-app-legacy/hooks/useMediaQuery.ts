import { useCallback, useSyncExternalStore } from "react";

/** Matches Tailwind's `lg` breakpoint. */
export const DESKTOP_QUERY = "(min-width: 64rem)";

export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    [query],
  );
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches, () => false);
}
