import { fmtMoney } from "../shared/format";
// Fallback thresholds vs the 30-day average when the server has no quality class.
const SUNNY_RATIO = 0.85;
const POOR_RATIO = 0.55;
// Configured discharge floor for this installation (read-only estimate).
const INVERTER_DISCHARGE_FLOOR_PCT = 20;
export function tomorrowOf(days) {
    return days.find((day) => !day.today) ?? null;
}
export function dayKind(qual, kwh, avg30) {
    if (qual)
        return qual === "tốt" ? "sunny" : qual === "ít" ? "poor" : "mid";
    if (kwh == null || !avg30)
        return null;
    if (kwh >= avg30 * SUNNY_RATIO)
        return "sunny";
    if (kwh <= avg30 * POOR_RATIO)
        return "poor";
    return "mid";
}
export function batteryPlan(metrics, needKwh) {
    const soc = metrics?.battery_soc;
    const capacity = metrics?.battery_capacity_kwh;
    if (soc == null || !capacity)
        return null;
    const reserve = INVERTER_DISCHARGE_FLOOR_PCT;
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
// ---------- "Do now" suggestions ----------
// kW of spare sun above the load before running heavy appliances is "free".
const SURPLUS_KW = 1.2;
const BATTERY_FULL_PCT = 95;
export function buildSuggestions({ metrics, kind, tier, hour, }) {
    const out = [];
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
    }
    else if (hour < 8 && kind === "sunny") {
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
    if (tier && tier.prices.length && hour >= 18 && hour < 23 && plan && plan.usableKwh < 3) {
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
const BEST_WINDOW_FIRST_HOUR = 6;
const BEST_WINDOW_LAST_HOUR = 18;
const BEST_WINDOW_MIN_HOURS = 2;
export function hourCells(hours) {
    const readings = new Map(hours.map(point => [point.hour, point]));
    return Array.from({length: 24}, (_, hour) => {
        const point = readings.get(hour);
        let level = "none";
        if (Number.isFinite(point?.grid) && point.n !== 0) {
            if (point.grid <= CHEAP_GRID_W && Number.isFinite(point.pv) && point.pv > 0 && Number.isFinite(point.load) && point.pv >= point.load) {
                level = "cheap";
            } else {
                level = point.grid <= MID_GRID_W ? "mid" : "dear";
            }
        }
        return {hour, level};
    });
}

// Longest run of cheap daytime hours, if at least two hours long.
export function bestWindow(cells) {
    let best = null;
    let runStart = -1;
    for (const cell of cells) {
        const cheap = cell.hour >= BEST_WINDOW_FIRST_HOUR && cell.hour <= BEST_WINDOW_LAST_HOUR && cell.level === "cheap";
        if (!cheap) {
            runStart = -1;
            continue;
        }
        if (runStart < 0)
            runStart = cell.hour;
        const length = cell.hour + 1 - runStart;
        if (!best || length > best.to - best.from)
            best = { from: runStart, to: cell.hour + 1 };
    }
    return best && best.to - best.from >= BEST_WINDOW_MIN_HOURS ? best : null;
}
