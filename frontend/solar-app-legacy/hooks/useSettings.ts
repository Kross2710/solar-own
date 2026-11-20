import { useCallback, useSyncExternalStore } from "react";
import useSWR from "swr";
import { apiUrl, fetcher } from "@/lib/api";
import { StatusResponse } from "@/lib/types/system";

// Poll quickly only while a sync is running, so its result shows up without a reload.
const SYNC_POLL_MS = 3000;

export function useStatus(active: boolean) {
  return useSWR<StatusResponse>(active ? apiUrl("/api/status") : null, fetcher, {
    refreshInterval: (latest) => (latest?.sync.running ? SYNC_POLL_MS : 0),
  });
}

// ---------- text size ----------

export type FontScale = "1" | "lg" | "xl";

// Same key and attribute as the old dashboard, so a saved choice carries over.
export const FONT_SCALE_KEY = "fontscale";
const FONT_SCALE_EVENT = "fontscale-change";

function readFontScale(): FontScale {
  try {
    const value = localStorage.getItem(FONT_SCALE_KEY);
    return value === "lg" || value === "xl" ? value : "1";
  } catch {
    return "1";
  }
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(FONT_SCALE_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(FONT_SCALE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function useFontScale(): [FontScale, (value: FontScale) => void] {
  const scale = useSyncExternalStore(subscribe, readFontScale, () => "1" as FontScale);

  const setScale = useCallback((value: FontScale) => {
    try {
      localStorage.setItem(FONT_SCALE_KEY, value);
    } catch {
      // Private mode: the choice still applies until reload.
    }
    if (value === "1") document.documentElement.removeAttribute("data-fontscale");
    else document.documentElement.setAttribute("data-fontscale", value);
    window.dispatchEvent(new Event(FONT_SCALE_EVENT));
  }, []);

  return [scale, setScale];
}
