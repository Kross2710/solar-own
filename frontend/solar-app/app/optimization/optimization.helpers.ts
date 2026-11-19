import { siteClock, siteTime } from "@/lib/time";
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
  const label = kind === "sunny" ? "Higher output tomorrow" : kind === "poor" ? "Lower output tomorrow" : "Typical output tomorrow";
  return kwh != null ? `${label} · ~${Math.round(kwh)} kWh` : label;
}

export interface BatteryPlan {
  socPct: number;
  storedKwh: number;
  needKwh: number | null;     // typical overnight consumption
}

export function batteryPlan(metrics: MetricsResponse | undefined, needKwh: number | null): BatteryPlan | null {
  const soc = metrics?.battery_soc;
  const capacity = metrics?.battery_capacity_kwh;
  if (soc == null || !capacity) return null;

  const storedKwh = (soc / 100) * capacity;
  return {
    socPct: soc,
    storedKwh,
    needKwh,
  };
}

// Below this the battery is treated as idle (inverter standby draw).
const BATTERY_IDLE_W = 50;
// Charge that would finish after this hour is too slow to count as "full today".
const SUN_LAST_HOUR = 18;
const ROUND_MIN = 10;

export interface BatteryOutlook {
  title: string;
  detail: string;
}

function clockIn(now: Date, minutes: number): Date {
  return new Date(Math.round((now.getTime() + minutes * 60_000) / (ROUND_MIN * 60_000)) * ROUND_MIN * 60_000);
}

function fmtClock(at: Date): string {
  return siteTime(at);
}

// Current battery flow and estimated finish time while charging.
export function batteryOutlook(metrics: MetricsResponse | undefined, now: Date): BatteryOutlook | null {
  const soc = metrics?.battery_soc;
  const capacity = metrics?.battery_capacity_kwh;
  if (soc == null || !capacity) return null;

  const battKw = (metrics?.battery_power_w ?? 0) / 1000;

  if (battKw * 1000 < -BATTERY_IDLE_W) {
    return { title: `Discharging · ${soc}%`, detail: `supplying ${(-battKw).toFixed(1)} kW` };
  }

  if (battKw * 1000 > BATTERY_IDLE_W) {
    const minutes = (((100 - soc) / 100) * capacity / battKw) * 60;
    const fullAt = clockIn(now, minutes);
    if (siteClock(fullAt).day !== siteClock(now).day || siteClock(fullAt).hour >= SUN_LAST_HOUR) {
      return { title: `Charging · ${soc}%`, detail: `${battKw.toFixed(1)} kW — too slow to fill today` };
    }
    return { title: `Full around ${fmtClock(fullAt)}`, detail: `charging ${battKw.toFixed(1)} kW · ${soc}% now` };
  }

  if (soc >= BATTERY_FULL_PCT) return { title: `Battery full · ${soc}%`, detail: "idle" };
  return {
    title: `Battery ${soc}%`,
    detail: "idle",
  };
}

export function planAdvice(kind: DayKind | null): string {
  if (!kind) return "Waiting for tomorrow’s forecast…";
  if (kind === "poor") return "Lower solar output is expected tomorrow. Consider postponing flexible loads.";
  if (kind === "sunny") return "Shift flexible loads into tomorrow’s sunny hours.";
  return "Plan flexible loads around tomorrow’s solar production.";
}

// ---------- "Do now" suggestions ----------

// kW of spare sun above the load before running heavy appliances is "free".
const SURPLUS_KW = 1.2;
const BATTERY_FULL_PCT = 95;
// Within this many kWh of the next tier, evening kWh are priced at the next tier.


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

  if (surplusKw > SURPLUS_KW && batteryFull && hour >= 8 && hour <= 16) {
    out.push({
      id: "wash-now",
      icon: "fa-shirt",
      tone: "load",
      title: "Use spare solar for a flexible load",
      detail: `${surplusKw.toFixed(1)} kW of spare sun — use it for a load you would otherwise run later`,
      when: "Now",
      isNow: true,
      value: "Spare sun",
      valueTone: "good",
    });
  } else if (hour < 8 && kind === "sunny") {
    out.push({
      id: "wash-later",
      icon: "fa-shirt",
      tone: "load",
      title: "Batch heavy loads into 10:00–14:00",
      detail: "usually the sunniest window — check live surplus before starting",
      when: "10–14h",
      isNow: false,
      value: "Spare sun",
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
      value: "Shift load",
      valueTone: "neutral",
    });
  }

  const plan = batteryPlan(metrics, null);
  if (tier && tier.prices.length && hour >= 18 && hour < 23 && plan && plan.storedKwh < 3) {
    const price = tier.cur_price;
    out.push({
      id: "avoid-evening",
      icon: "fa-plug-circle-xmark",
      tone: "warn",
      title: "Battery low — move flexible loads to daylight",
      detail: "estimated grid price at projected cycle use; residential rates do not change by hour",
      when: "This evening",
      isNow: true,
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

export function hourCells(hours: HourlyPoint[], marginal: number | null): HourCell[] {
  const heavyCost = marginal == null ? null : fmtMoney(Math.round(HEAVY_LOAD_KW * marginal));

  return hours.map(({ hour, pv, load, grid }) => {
    if (grid == null) return { hour, level: "none", description: "no data yet", cost: "" };
    if (grid <= CHEAP_GRID_W && (pv ?? 0) >= (load ?? 0)) {
      return { hour, level: "cheap", description: "usually supplied by solar", cost: "check live surplus" };
    }
    if (grid <= MID_GRID_W) return { hour, level: "mid", description: "the battery covers it", cost: "uses tonight's charge" };
    return { hour, level: "dear", description: "buying from the grid", cost: heavyCost == null ? "grid price unavailable" : `1.5kW ~${heavyCost}/h at projected use` };
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
  const clock = siteClock(now);
  const minutes = clock.hour * 60 + clock.minute;
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
  return DAY_NAMES[new Date(`${iso}T00:00:00Z`).getUTCDay()];
}

export interface WeatherIcon {
  icon: string;
  className: string;
}

export function weatherIcon(code: number | null | undefined): WeatherIcon {
  const amber = "text-pv";
  const gray = "text-zinc-500";
  const blue = "text-load";
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
