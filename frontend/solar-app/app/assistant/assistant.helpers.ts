import { fmtMoney, fmtNum, parseDateMonth } from "@/lib/format";
import { MetricsResponse } from "@/lib/types";
import { ChatEntry, ChatStreamEvent, Notice, ProposedAction } from "@/lib/types/assistant";

// Each question is also the prompt sent to the model, so it must read as a real question.
// They ask what the screen can't answer at a glance.
export interface SuggestedQuestion {
  q: string;
  icon: string;
  color: string;
}

export const SUGGESTED_QUESTIONS: SuggestedQuestion[] = [
  { q: "Why is my projected bill high?", icon: "fa-receipt", color: "#fb8a95" },
  { q: "Am I close to the expensive price tier?", icon: "fa-arrow-trend-up", color: "#ffc76b" },
  { q: "Anything unusual in the last few days?", icon: "fa-magnifying-glass", color: "#7dd3fc" },
  { q: "How does this month compare to last month?", icon: "fa-chart-line", color: "#34d399" },
];

// Battery power (W) beyond which it counts as charging / discharging.
const BATTERY_IDLE_W = 30;

export function greeting(metrics: MetricsResponse | undefined): string {
  if (metrics?.battery_soc == null) {
    return "Hi! Ask me about your home's power — savings, bills, or when to run appliances.";
  }
  const power = metrics.battery_power_w ?? 0;
  const state = power > BATTERY_IDLE_W ? ", charging" : power < -BATTERY_IDLE_W ? ", powering the house" : "";
  return `Everything is running normally. Battery ${Math.round(metrics.battery_soc)}%${state}. Tap a question below, or ask me anything about your home's power.`;
}

const TOOL_LABELS: Record<string, string> = {
  get_day_detail: "Checking that day's hour-by-hour data…",
  get_daily_history: "Going through your daily history…",
  get_cycle_report: "Opening the billing cycle report…",
  get_curtailment: "Checking wasted sunshine…",
  get_weather_forecast: "Checking the weather forecast…",
  get_hourly_profile: "Looking at your usual day, hour by hour…",
  propose_action: "Preparing a suggestion…",
};

export function toolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? "Looking up your data…";
}

export function errorText(code: string | null): string {
  if (code === "rate_limit") return "You're asking a bit fast — try again in a moment.";
  if (code === "network") return "Network error — try again later.";
  if (code) return "The assistant hit an error — try again later.";
  return "No reply yet — please try again.";
}

export function actionLabel(action: ProposedAction): string {
  if (action.kind === "set_reserve" && action.params.reserve_pct != null) {
    return `Change battery reserve from ${fmtNum(action.current)}% to ${fmtNum(action.params.reserve_pct)}%`;
  }
  return action.kind;
}

export const ACTION_NOTE = "Used for dashboard calculations — nothing is written to the inverter.";

export interface NoticeView {
  icon: string;
  title: string;
  detail: string;
  // Prompt for "Ask about this": carries the numbers so the model starts from the same facts.
  ask: string;
}

export function noticeView(notice: Notice): NoticeView {
  switch (notice.kind) {
    case "offline":
      return {
        icon: "fa-plug-circle-xmark",
        title: "The solar system isn't reporting",
        detail: `No data since ${notice.data.since.slice(11)}. Check the inverter's Wi-Fi or power.`,
        ask: `The solar system stopped reporting at ${notice.data.since.slice(11)}. What should I check?`,
      };
    case "night_load_high":
      return {
        icon: "fa-moon",
        title: `Last night used ~${fmtNum(notice.data.night_kwh)} kWh`,
        detail: `Well above the usual ${fmtNum(notice.data.avg_kwh)} kWh. Was something left running?`,
        ask: `Last night (${parseDateMonth(notice.data.night)}) the house used about ${fmtNum(notice.data.night_kwh)} kWh vs the usual ${fmtNum(notice.data.avg_kwh)} kWh. What could explain it?`,
      };
    case "bill_high":
      return {
        icon: "fa-receipt",
        title: `Bill heading to ~${fmtMoney(notice.data.proj)}`,
        detail: `${notice.data.pct}% more than the last real EVN bill (${fmtMoney(notice.data.last)}).`,
        ask: `This cycle's bill is heading to about ${fmtMoney(notice.data.proj)}, ${notice.data.pct}% more than the last EVN bill. Why, and what can I do?`,
      };
    case "tier_ahead": {
      const when = notice.data.days_left != null ? `in about ${notice.data.days_left} days` : "before the cycle ends";
      return {
        icon: "fa-arrow-trend-up",
        title: `Tier ${notice.data.tier} price ${when}`,
        detail: `At this pace, grid power goes from ${fmtMoney(notice.data.cur_price)} to ${fmtMoney(notice.data.price)}/kWh after ${fmtNum(notice.data.to_next_kwh)} more kWh.`,
        ask: `I'm about ${fmtNum(notice.data.to_next_kwh)} kWh away from the ${fmtMoney(notice.data.price)}/kWh price. How can I stay below it this cycle?`,
      };
    }
    case "wasted_sun_up":
      return {
        icon: "fa-sun",
        title: `~${fmtNum(notice.data.lost_kwh)} kWh of sun wasted this week`,
        detail: `Up from ~${fmtNum(notice.data.prev_kwh)} kWh the week before — about ${fmtMoney(notice.data.value)}${
          notice.data.full_at ? `. Battery usually full by ${notice.data.full_at}` : ""
        }.`,
        ask: `This week about ${fmtNum(notice.data.lost_kwh)} kWh of sunshine went unused, up from ${fmtNum(notice.data.prev_kwh)} kWh. How can I use more of it?`,
      };
  }
}

// ---------- chat stream ----------

// Split a raw SSE buffer into complete events; the incomplete tail is returned for the next read.
export function parseSse(buffer: string): { events: ChatStreamEvent[]; rest: string } {
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: ChatStreamEvent[] = [];
  for (const block of blocks) {
    const line = block.split("\n").find((l) => l.startsWith("data: "));
    if (!line) continue;
    try {
      events.push(JSON.parse(line.slice(6)));
    } catch {
      // A malformed event is skipped rather than breaking the whole reply.
    }
  }
  return { events, rest };
}

// The model only sees plain turns; greetings and action cards are UI-only.
export function toApiMessages(entries: ChatEntry[]): { role: string; content: string }[] {
  return entries.flatMap((entry) =>
    entry.type === "message" && !entry.error ? [{ role: entry.role, content: entry.content }] : [],
  );
}

let idCounter = 0;
export function entryId(): string {
  idCounter += 1;
  return `${Date.now().toString(36)}-${idCounter}`;
}
