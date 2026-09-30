import { fmtMoney } from "@/lib/format";
import { MetricsResponse } from "@/lib/types";
import { MoneyTier } from "@/lib/types/money";
import { ForecastDay, ForecastQual, HourlyPoint } from "@/lib/types/optimization";

// ---------- tomorrow & battery plan ----------

export type DayKind = "sunny" | "mid" | "poor";

// Fallback thresholds vs the 30-day average when the server has no quality class.
const SUNNY_RATIO = 0.85;
const POOR_RATIO = 0.55;
const QUAL_STORAGE_KEY = "battQual";
const DEFAULT_RESERVE_PCT = 20;

export function tomorrowOf(days: ForecastDay[]): ForecastDay | null {
  return days.find((day) => !day.today) ?? null;
}

// Pin tomorrow's quality label once per target date so it doesn't flip during the day
// as the forecast refreshes.
export function lockedQual(date: string, qual: ForecastQual | undefined): ForecastQual | null {
  if (qual == null) return null;
  try {
    const raw = window.localStorage.getItem(QUAL_STORAGE_KEY);
    if (raw) {
      const stored = JSON.parse(raw) as { d?: string; q?: string };
      if (stored.d === date && (stored.q === "tốt" || stored.q === "vừa" || stored.q === "ít")) {
        return stored.q;
      }
    }
    window.localStorage.setItem(QUAL_STORAGE_KEY, JSON.stringify({ d: date, q: qual }));
  } catch {
    // Storage unavailable (private mode): fall back to the live label.
  }
  return qual;
}

export function dayKind(qual: ForecastQual | null, kwh: number | null, avg30: number | null): DayKind | null {
  if (qual) return qual === "tốt" ? "sunny" : qual === "ít" ? "poor" : "mid";
  if (kwh == null || !avg30) return null;
  if (kwh >= avg30 * SUNNY_RATIO) return "sunny";
  if (kwh <= avg30 * POOR_RATIO) return "poor";
  return "mid";
}

export function planTitle(kind: DayKind | null, kwh: number | null): string {
  if (!kind) return "Tomorrow's forecast";
  const label = kind === "sunny" ? "Sunny tomorrow" : kind === "poor" ? "Little sun tomorrow" : "Fair sun tomorrow";
  return kwh != null ? `${label} · ~${Math.round(kwh)} kWh` : label;
}

export interface BatteryPlan {
  socPct: number;
  reservePct: number;
  capacityKwh: number;
  usableKwh: number;          // above the reserve, right now
  needKwh: number | null;     // typical overnight consumption
  enough: boolean | null;
}

export function batteryPlan(metrics: MetricsResponse | undefined, needKwh: number | null): BatteryPlan | null {
  const soc = metrics?.battery_soc;
  const capacity = metrics?.battery_capacity_kwh;
  if (soc == null || !capacity) return null;

  const reserve = metrics?.battery_reserve_percent ?? DEFAULT_RESERVE_PCT;
  const usable = Math.max(0, ((soc - reserve) / 100) * capacity);
  return {
    socPct: soc,
    reservePct: reserve,
    capacityKwh: capacity,
    usableKwh: usable,
    needKwh,
    enough: needKwh == null ? null : usable >= needKwh,
  };
}

export function planAdvice(kind: DayKind | null, enough: boolean | null): string {
  if (!kind) return "Waiting for tomorrow's forecast to suggest tonight's battery plan…";
  if (enough === false) {
    return kind === "sunny"
      ? "Use the battery tonight and recharge tomorrow — it covers part of the night, the grid covers the rest."
      : "Save the battery and avoid heavy loads tonight — it won't last the night, the grid covers the rest.";
  }
  if (kind === "sunny") {
    return `Use the battery freely tonight${enough ? " — it will last the night" : ""}, it recharges tomorrow morning.`;
  }
  if (kind === "poor") return "Save the battery for tomorrow morning — avoid heavy loads tonight.";
  return "Use the battery normally, keep it around the reserve level.";
}

// ---------- "Do now" suggestions ----------

// kW of spare sun above the load before running heavy appliances is "free".
const SURPLUS_KW = 1.2;
const BATTERY_FULL_PCT = 95;
// Within this many kWh of the next tier, evening kWh are priced at the next tier.
const TIER_NEAR_KWH = 30;

export type SuggestionTone = "load" | "batt" | "warn";

export interface Suggestion {
  id: string;
  icon: string;               // Font Awesome class
  tone: SuggestionTone;
  title: string;
  detail: string;
  when: string;
  isNow: boolean;
  value: string;
  valueTone: "good" | "bad" | "neutral";
}

export function buildSuggestions({
  metrics,
  kind,
  tier,
  hour,
}: {
  metrics: MetricsResponse | undefined;
  kind: DayKind | null;
  tier: MoneyTier | undefined;
  hour: number;
}): Suggestion[] {
  const out: Suggestion[] = [];
  const pv = metrics?.pv_power_w ?? 0;
  const load = metrics?.load_power_w ?? 0;
  const surplusKw = (pv - load) / 1000;
  const batteryFull = (metrics?.battery_soc ?? 0) >= BATTERY_FULL_PCT;

  if (surplusKw > SURPLUS_KW && hour >= 8 && hour <= 16) {
    out.push({
      id: "wash-now",
      icon: "fa-shirt",
      tone: "load",
      title: "Run the washer + dryer now",
      detail: `${surplusKw.toFixed(1)} kW of spare sun — running them is free`,
      when: "Now",
      isNow: true,
      value: "0 đ",
      valueTone: "good",
    });
  } else if (hour < 8 && (kind === "sunny" || batteryFull)) {
    out.push({
      id: "wash-later",
      icon: "fa-shirt",
      tone: "load",
      title: "Batch heavy loads into 10:00–14:00",
      detail: "the sunniest window — powered by sun, costs nothing",
      when: "10–14h",
      isNow: false,
      value: "0 đ",
      valueTone: "good",
    });
  }

  if (hour >= 10 && hour < 15 && pv > 1000) {
    out.push({
      id: "pre-cool",
      icon: "fa-temperature-arrow-down",
      tone: "batt",
      title: "Pre-cool the house before 15:00",
      detail: "drop the AC 1–2° while the sun is out, so the battery works less tonight",
      when: "Before 15h",
      isNow: true,
      value: "−15%",
      valueTone: "neutral",
    });
  }

  if (tier && tier.prices.length) {
    const nearNext = tier.to_next_kwh != null && tier.to_next_kwh < TIER_NEAR_KWH;
    const price = tier.prices[Math.min(tier.index + (nearNext ? 1 : 0), tier.prices.length - 1)];
    const tierNumber = Math.min(tier.index + (nearNext ? 2 : 1), tier.count);
    out.push({
      id: "avoid-evening",
      icon: "fa-plug-circle-xmark",
      tone: "warn",
      title: "Avoid 21:00–23:00",
      detail: `battery running low — each kWh then costs tier ${tierNumber} price`,
      when: "21–23h",
      isNow: hour >= 21 && hour < 23,
      value: `${fmtMoney(price)}/kWh`,
      valueTone: "bad",
    });
  }

  return out.sort((a, b) => Number(b.isNow) - Number(a.isNow));
}

// ---------- best hours ----------

// Average grid draw (W) per hour: at or below CHEAP with PV above load the sun covers it;
// otherwise up to MID the battery does, which is energy the night then buys from the grid.
const CHEAP_GRID_W = 50;
const MID_GRID_W = 700;
const HEAVY_LOAD_KW = 1.5;
const BEST_WINDOW_FIRST_HOUR = 6;
const BEST_WINDOW_LAST_HOUR = 18;
const BEST_WINDOW_MIN_HOURS = 2;

export type HourLevel = "cheap" | "mid" | "dear" | "none";

export interface HourCell {
  hour: number;
  level: HourLevel;
  description: string;
  cost: string;
}

export function hourCells(hours: HourlyPoint[], marginal: number): HourCell[] {
  const heavyCost = fmtMoney(Math.round(HEAVY_LOAD_KW * marginal));

  return hours.map(({ hour, pv, load, grid }) => {
    if (grid == null) return { hour, level: "none", description: "no data yet", cost: "" };
    if (grid <= CHEAP_GRID_W && (pv ?? 0) >= (load ?? 0)) {
      return { hour, level: "cheap", description: "spare sun covers it", cost: "≈ 0 đ" };
    }
    if (grid <= MID_GRID_W) return { hour, level: "mid", description: "the battery covers it", cost: "uses tonight's charge" };
    return { hour, level: "dear", description: "buying from the grid", cost: `running 1.5kW ~${heavyCost}/h` };
  });
}

export interface HourWindow {
  from: number;
  to: number;                 // exclusive
}

// Longest run of cheap daytime hours, if at least two hours long.
export function bestWindow(cells: HourCell[]): HourWindow | null {
  let best: HourWindow | null = null;
  let runStart = -1;

  for (const cell of cells) {
    const cheap = cell.hour >= BEST_WINDOW_FIRST_HOUR && cell.hour <= BEST_WINDOW_LAST_HOUR && cell.level === "cheap";
    if (!cheap) {
      runStart = -1;
      continue;
    }
    if (runStart < 0) runStart = cell.hour;
    const length = cell.hour + 1 - runStart;
    if (!best || length > best.to - best.from) best = { from: runStart, to: cell.hour + 1 };
  }

  return best && best.to - best.from >= BEST_WINDOW_MIN_HOURS ? best : null;
}

// Minutes left in the window if `now` falls inside it.
export function minutesLeftInWindow(window: HourWindow, now: Date): number | null {
  const minutes = now.getHours() * 60 + now.getMinutes();
  if (minutes < window.from * 60 || minutes >= window.to * 60) return null;
  return window.to * 60 - minutes;
}

export function fmtDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours <= 0) return `${rest}m`;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

// ---------- 5-day forecast ----------

const FLAT_MIN_SPREAD_KWH = 2;
const FLAT_SPREAD_RATIO = 0.1;
const RAIN_SHOWN_FROM_PCT = 20;
const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export { RAIN_SHOWN_FROM_PCT };

// Near-identical days would look like a frozen app; the UI says so instead.
export function isFlatForecast(days: ForecastDay[]): boolean {
  const values = days.map((day) => day.kwh).filter((kwh): kwh is number => kwh != null);
  if (values.length < 2) return false;
  const max = Math.max(...values);
  return max - Math.min(...values) <= Math.max(FLAT_MIN_SPREAD_KWH, max * FLAT_SPREAD_RATIO);
}

export function dayOfWeek(iso: string): string {
  return DAY_NAMES[new Date(`${iso}T00:00:00`).getDay()];
}

export interface WeatherIcon {
  icon: string;
  className: string;
}

export function weatherIcon(code: number | null | undefined): WeatherIcon {
  const amber = "text-[#ffc76b]";
  const gray = "text-zinc-500";
  const blue = "text-[#7dd3fc]";
  if (code == null) return { icon: "fa-cloud-sun", className: amber };
  if (code === 0) return { icon: "fa-sun", className: amber };
  if (code <= 2) return { icon: "fa-cloud-sun", className: amber };
  if (code === 3) return { icon: "fa-cloud", className: gray };
  if (code <= 48) return { icon: "fa-smog", className: gray };
  if (code <= 67) return { icon: "fa-cloud-rain", className: blue };
  if (code <= 77) return { icon: "fa-snowflake", className: blue };
  if (code <= 82) return { icon: "fa-cloud-showers-heavy", className: blue };
  return { icon: "fa-cloud-bolt", className: blue };
}
