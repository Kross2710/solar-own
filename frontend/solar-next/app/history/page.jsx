import {pageMetadata} from "../i18n/metadata";
import History from "./History";

export const dynamic = "force-dynamic";

const example = Array.from({ length: 50 }, (_, index) => {
  const kwh = Math.round(31 + 10 * Math.sin(index * 1.8) + 6 * Math.cos(index / 3));
  const buy = Math.round(13 - 6 * Math.sin(index * 1.8));
  const lost_kwh = index % 11 === 0 ? null : Math.max(0, Math.round((kwh - 22) * 4) / 10);
  return { lost_kwh, day: new Date(Date.UTC(2026, 9, 1 + index)).toISOString().slice(0, 10), kwh, buy, cons:buy+kwh-4, batt:6 };
});

async function readDays() {
  const backend = process.env.BACKEND_URL || "http://127.0.0.1:8787";
  const response = await fetch(new URL("/api/daily?days=366&include_unused_solar=true", backend), {
    cache: "no-store", signal: AbortSignal.timeout(8000)
  });
  if (!response.ok) throw new Error("History unavailable");
  const rows = await response.json();
  if (!Array.isArray(rows)) throw new Error("Invalid history");
  return rows.filter(row => /^\d{4}-\d{2}-\d{2}$/.test(row?.day));
}

export default async function Page({ searchParams }) {
  const demo = (await searchParams).demo === "1";
  let rows;
  if (demo) rows = example;
  else {
    try { rows = await readDays(); }
    catch { rows = null; }
  }
  return <History rows={rows} demo={demo} />;
}

export const generateMetadata = () => pageMetadata("History");
