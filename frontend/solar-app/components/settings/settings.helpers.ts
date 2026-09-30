import { parseDateMonth, parseDateMonthYear } from "@/lib/format";
import { StatusResponse, SyncResult } from "@/lib/types/system";

export const RESERVE_MIN_PCT = 10;
export const RESERVE_MAX_PCT = 80;
export const RESERVE_STEP_PCT = 5;

export function clampReserve(value: number): number {
  return Math.min(RESERVE_MAX_PCT, Math.max(RESERVE_MIN_PCT, Math.round(value)));
}

const STEP_NAMES: Record<string, string> = {
  sems_daily: "daily history",
  samples: "minute curve",
  curtailment: "wasted sun",
  prune: "cleanup",
};

// "12:08" today, "Sep 29, 12:08" otherwise; the backend sends Vietnam time with an offset.
export function fmtWhen(iso: string, now: Date = new Date()): string {
  const day = iso.slice(0, 10);
  const time = iso.slice(11, 16);
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(now);
  return day === today ? `today ${time}` : `${parseDateMonth(day)}, ${time}`;
}

export function syncSummary(sync: StatusResponse["sync"], now?: Date): string {
  if (!sync.supported) return "This data source has no history to sync.";
  if (sync.running) return "Syncing with SEMS…";
  const last: SyncResult | null = sync.last;
  if (!last?.finished_at) return "Not synced since the server started.";
  const when = `Last synced ${fmtWhen(last.finished_at, now)}`;
  if (last.errors.length) {
    return `${when} — ${last.errors.map((step) => STEP_NAMES[step] ?? step).join(", ")} failed.`;
  }
  return `${when} · took ${last.seconds ?? 0}s`;
}

export function historyLine(history: StatusResponse["history"]): string {
  if (!history.days || !history.first_day) return "No daily history yet";
  return `${history.days} days since ${parseDateMonthYear(history.first_day)}`;
}

export function evnLine(evn: StatusResponse["evn"]): string {
  if (!evn.enabled) return "Off";
  if (!evn.last_day) return "Waiting for the first sync";
  return `Meter up to ${parseDateMonth(evn.last_day)} · ${evn.bills} bills`;
}

export function forecastLine(forecast: StatusResponse["forecast"]): string {
  if (!forecast.ready) return "Still learning";
  const mae = forecast.mae_kwh != null ? ` · ±${forecast.mae_kwh.toFixed(1)} kWh/day` : "";
  const trained = forecast.updated_at ? ` · trained ${parseDateMonth(forecast.updated_at)}` : "";
  return `${forecast.model}${mae}${trained}`;
}
