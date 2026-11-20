const fields = [
  "status", "timestamp", "source", "pv_power_w", "load_power_w", "battery_power_w",
  "grid_power_w", "battery_soc", "today_energy_kwh", "today_consumption_kwh",
  "today_buy_kwh", "capacity_kw", "battery_capacity_kwh"
];

export function publicReading(data) {
  if (!data || typeof data.status !== "string") return null;
  const reading = Object.fromEntries(fields.map(key => [key, data[key] ?? null]));
  return {...reading, hasError: Boolean(data.error)};
}

export const siteDay = time => new Intl.DateTimeFormat("sv-SE", {
  timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit"
}).format(time);

export const siteTime = time => new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", minute: "2-digit", hourCycle:"h23"
}).format(time);

export function power(watts, lang="en") {
  if (!Number.isFinite(watts)) return "—";
  const n = Math.abs(watts);
  return n < 1000 ? Math.round(n) + " W" : (n / 1000).toLocaleString(lang==="vi"?"vi-VN":"en-GB",{minimumFractionDigits:2,maximumFractionDigits:2}) + " kW";
}

export function selfShare(cons, buy) {
  if (!Number.isFinite(cons) || !Number.isFinite(buy) || cons <= 0 || buy < 0 || buy > cons) return null;
  return Math.round(100 * (1 - buy / cons));
}
