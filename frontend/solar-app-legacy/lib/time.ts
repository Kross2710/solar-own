export const SITE_TZ = "Asia/Ho_Chi_Minh";

const clockFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: SITE_TZ, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit",
});

export function siteClock(now: Date = new Date()) {
  const parts = clockFormatter.formatToParts(now);
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)!.value;
  return { day: `${get("year")}-${get("month")}-${get("day")}`, hour: Number(get("hour")), minute: Number(get("minute")) };
}

export function siteTime(now: Date): string {
  const { hour, minute } = siteClock(now);
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}
