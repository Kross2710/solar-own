"use client";

import { siteClock } from "@/lib/time";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { cycleCountdownLabel, isTooEarlyToProject } from "@/app/money/money.helpers";
import {
  batteryOutlook,
  buildSuggestions,
  dayKind,
  DayKind,
  lockedQual,
  planTitle,
  RAIN_SHOWN_FROM_PCT,
  tomorrowOf,
  weatherIcon,
} from "@/app/optimization/optimization.helpers";
import Card from "@/components/Card";
import { useMoney } from "@/hooks/useMoney";
import { useForecast } from "@/hooks/useOptimization";
import { fmtMoneyShort } from "@/lib/format";
import { MetricsResponse } from "@/lib/types";
import { ForecastResponse } from "@/lib/types/optimization";

// From this hour, with no sun left, the card looks at tomorrow instead of today.
const EVENING_HOUR = 15;
const SUN_UP_W = 100;

const KIND_ICONS: Record<DayKind, string> = { sunny: "fa-sun", mid: "fa-cloud-sun", poor: "fa-cloud" };

const TONES = {
  batt: "bg-batt/10 text-batt ring-batt/30",
  pv: "bg-pv/10 text-pv ring-pv/30",
  good: "bg-good/10 text-good ring-good/30",
  load: "bg-load/10 text-load ring-load/30",
};

function useNow(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(timer);
  }, []);
  return now;
}

function Row({
  href,
  icon,
  tone,
  title,
  detail,
}: {
  href: string;
  icon: string;
  tone: keyof typeof TONES;
  title: string;
  detail: string;
}) {
  return (
    <li>
      <Link className="flex items-center gap-3 py-2.5 transition hover:text-zinc-50" href={href}>
        <span className={`grid size-9 shrink-0 place-items-center rounded-xl ring-1 ring-inset ${TONES[tone]}`}>
          <i className={`fa-solid ${icon}`} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[13px] font-semibold leading-snug text-zinc-100">{title}</span>
          <span className="mt-0.5 block text-[11px] tabular-nums text-zinc-400 first-letter:uppercase">{detail}</span>
        </span>
        <i className="fa-solid fa-chevron-right text-[10px] text-zinc-500" />
      </Link>
    </li>
  );
}

type ReadyForecast = Extract<ForecastResponse, { ready: true }>;

// Daytime: today's output against the forecast. Evening: what tomorrow looks like.
function sunRow(
  metrics: MetricsResponse,
  forecast: ReadyForecast,
  hour: number,
  tomorrowTitle: string,
  kind: DayKind | null,
) {
  const pvWatt = metrics.pv_power_w ?? 0;
  const producedKwh = metrics.today_energy_kwh ?? 0;

  if (hour >= EVENING_HOUR && pvWatt < SUN_UP_W) {
    const tomorrow = tomorrowOf(forecast.days);
    if (!tomorrow) return null;
    // Tropical rain chances run high even on good solar days, so they only back up a gloomy forecast.
    const rain = tomorrow.rain_prob ?? 0;
    const details = [`made ${producedKwh.toFixed(1)} kWh today`];
    if (forecast.avg30_kwh != null) details.push(`30-day avg ${Math.round(forecast.avg30_kwh)}`);
    if (kind !== "sunny" && rain >= RAIN_SHOWN_FROM_PCT) details.push(`${rain}% rain`);
    return {
      icon: kind ? KIND_ICONS[kind] : weatherIcon(tomorrow.wcode).icon,
      title: tomorrowTitle,
      detail: details.join(" · "),
    };
  }

  const today = forecast.days.find((day) => day.today);
  if (!today?.kwh) return null;
  const expected = Math.round(today.kwh);
  return {
    icon: weatherIcon(today.wcode).icon,
    title: producedKwh < 0.5 ? `~${expected} kWh expected today` : `${producedKwh.toFixed(1)} of ~${expected} kWh expected`,
    detail: pvWatt >= SUN_UP_W ? `generating ${(pvWatt / 1000).toFixed(1)} kW now` : "waiting for the sun",
  };
}

export default function TodayCard({ metrics }: { metrics: MetricsResponse }) {
  const now = useNow();
  const hour = siteClock(now).hour;
  const { money, isLoading: moneyLoading } = useMoney();
  const { data: forecast } = useForecast();

  const ready = forecast?.ready ? forecast : null;
  const tomorrow = ready ? tomorrowOf(ready.days) : null;
  const kind = useMemo(() => {
    const qual = tomorrow ? lockedQual(tomorrow.date, tomorrow.qual) : null;
    return dayKind(qual, tomorrow?.kwh ?? null, ready?.avg30_kwh ?? null);
  }, [tomorrow, ready?.avg30_kwh]);

  const battery = batteryOutlook(metrics, now);
  const sun = ready ? sunRow(metrics, ready, hour, planTitle(kind, tomorrow?.kwh ?? null), kind) : null;
  const suggestion = buildSuggestions({ metrics, kind, tier: money?.projected_tier ?? money?.tier, hour })[0];
  const saved = money?.today.saved;
  const cycle = money?.cycle;

  return (
    <Card pad="p-4 sm:p-5" aria-labelledby="today-actions">
      <h2 className="text-sm font-bold text-zinc-100" id="today-actions">
        Today
      </h2>
      <ul className="mt-3 divide-y divide-white/5">
        {battery && (
          <Row href="/optimization" icon="fa-battery-half" tone="batt" title={battery.title} detail={battery.detail} />
        )}
        {sun && <Row href="/optimization" icon={sun.icon} tone="pv" title={sun.title} detail={sun.detail} />}
        <Row
          href="/money"
          icon="fa-coins"
          tone="good"
          title={
            moneyLoading && saved == null
              ? "Savings updating…"
              : saved == null
                ? "Today's savings"
                : `Saved today ~${fmtMoneyShort(saved)}`
          }
          detail={
            cycle
              ? `${isTooEarlyToProject(cycle) ? "EVN cycle" : `EVN bill ~${fmtMoneyShort(cycle.bill_proj)}`} · ${cycleCountdownLabel(cycle)}`
              : "Open Money"
          }
        />
        <Row
          href="/optimization"
          icon={suggestion?.icon ?? "fa-lightbulb"}
          tone="load"
          title={suggestion ? suggestion.title : "See what to do today"}
          detail={suggestion ? suggestion.detail : "Open Optimization"}
        />
      </ul>
    </Card>
  );
}
