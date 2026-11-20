import { siteClock } from "./time";

// Sunrise and sunset for a date and place (NOAA approximation, good to a few minutes).

const RAD = Math.PI / 180;
const DAY_MS = 86_400_000;
// Sun's center 0.833° below the horizon: refraction plus the solar disc radius.
const ZENITH = 90.833;

export interface SunTimes {
  rise: Date;
  set: Date;
}

export function sunTimes(date: Date, lat: number, lon: number): SunTimes | null {
  const [year, month, day] = siteClock(date).day.split("-").map(Number);
  const base = Date.UTC(year, month - 1, day);
  const dayOfYear = Math.round((base - Date.UTC(year, 0, 0)) / DAY_MS);
  const g = ((2 * Math.PI) / 365) * (dayOfYear - 1);

  const eqTime =
    229.18 *
    (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  const decl =
    0.006918 -
    0.399912 * Math.cos(g) +
    0.070257 * Math.sin(g) -
    0.006758 * Math.cos(2 * g) +
    0.000907 * Math.sin(2 * g) -
    0.002697 * Math.cos(3 * g) +
    0.00148 * Math.sin(3 * g);

  const cosH = Math.cos(ZENITH * RAD) / (Math.cos(lat * RAD) * Math.cos(decl)) - Math.tan(lat * RAD) * Math.tan(decl);
  if (cosH < -1 || cosH > 1) return null;
  const hourAngle = Math.acos(cosH) / RAD;

  // Minutes after UTC midnight of the local calendar date; negative values land on the day before.
  const riseMin = 720 - 4 * (lon + hourAngle) - eqTime;
  const setMin = 720 - 4 * (lon - hourAngle) - eqTime;
  return { rise: new Date(base + riseMin * 60_000), set: new Date(base + setMin * 60_000) };
}

export interface SkyPosition {
  day: boolean;
  /** 0 at sunrise (or sunset for the night arc), 1 at sunset (or the next sunrise). */
  progress: number;
}

export function skyPosition(now: Date, lat: number, lon: number): SkyPosition {
  const today = sunTimes(now, lat, lon);
  if (!today) return { day: true, progress: 0.5 };
  const t = now.getTime();
  const rise = today.rise.getTime();
  const set = today.set.getTime();

  if (t >= rise && t <= set) return { day: true, progress: (t - rise) / (set - rise) };
  // Night runs from yesterday's or today's sunset to the next sunrise; a day's length is close enough.
  const nightStart = t > set ? set : set - DAY_MS;
  const nightEnd = t > set ? rise + DAY_MS : rise;
  return { day: false, progress: (t - nightStart) / (nightEnd - nightStart) };
}
