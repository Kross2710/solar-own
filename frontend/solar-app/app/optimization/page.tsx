"use client";

import { siteClock } from "@/lib/time";

import { useEffect, useMemo, useState } from "react";
import DashboardShell from "@/components/DashboardShell";
import BestHoursCard from "@/components/optimization/BestHoursCard";
import DoNowCard from "@/components/optimization/DoNowCard";
import ForecastCard from "@/components/optimization/ForecastCard";
import TonightHero from "@/components/optimization/TonightHero";
import WastedSunCard from "@/components/optimization/WastedSunCard";
import { useMoney } from "@/hooks/useMoney";
import { useCurtailment, useForecast, useHourly, useMetrics } from "@/hooks/useOptimization";
import {
  batteryPlan,
  buildSuggestions,
  dayKind,
  hourCells,
  lockedQual,
  planAdvice,
  tomorrowOf,
} from "./optimization.helpers";

const CLOCK_TICK_MS = 60 * 1000;

function useNow(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), CLOCK_TICK_MS);
    return () => clearInterval(timer);
  }, []);
  return now;
}

export default function OptimizationPage() {
  const now = useNow();
  const { data: forecast, isLoading: forecastLoading } = useForecast();
  const { data: metrics, error: metricsError, isLoading: metricsLoading } = useMetrics();
  const { data: hourly } = useHourly();
  const { data: curtailment } = useCurtailment();
  const { money } = useMoney();

  const ready = forecast?.ready ? forecast : null;
  const tomorrow = ready ? tomorrowOf(ready.days) : null;
  const qual = useMemo(
    () => (tomorrow ? lockedQual(tomorrow.date, tomorrow.qual) : null),
    [tomorrow],
  );
  const kind = dayKind(qual, tomorrow?.kwh ?? null, ready?.avg30_kwh ?? null);
  const plan = batteryPlan(metrics, ready?.night_need_kwh ?? null);
  const suggestions = buildSuggestions({ metrics, kind, tier: money?.tier, hour: siteClock(now).hour });
  const cells = useMemo(() => (hourly ? hourCells(hourly.hours, hourly.marginal) : []), [hourly]);

  if (metricsLoading && forecastLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink font-sans text-zinc-400">
        Connecting to Solar...
      </div>
    );
  }

  if (metricsError && !forecast) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink font-sans text-grid-in">
        Can&apos;t get data from Backend
      </div>
    );
  }

  return (
    <DashboardShell status={metricsError ? "error" : "online"} source="">
      <div className="grid gap-7 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] xl:items-center">
        <TonightHero
          kind={kind}
          tomorrowKwh={tomorrow?.kwh ?? null}
          advice={planAdvice(kind, plan?.enough ?? null)}
          plan={plan}
        />
        <div className="flex flex-col gap-7">
          <DoNowCard suggestions={suggestions} />
          <BestHoursCard cells={cells} now={now} />
        </div>
      </div>
      <div className="grid gap-7 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] xl:items-start">
        {curtailment?.supported && <WastedSunCard data={curtailment} />}
        {ready && (
          <div className={curtailment?.supported ? "" : "xl:col-span-2"}>
            <ForecastCard days={ready.days} avg30={ready.avg30_kwh} mae={ready.quality.mae ?? null} />
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
