"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { buildSuggestions, dayKind, lockedQual, tomorrowOf } from "@/app/optimization/optimization.helpers";
import { useMoney } from "@/hooks/useMoney";
import Card from "@/components/Card";
import { useForecast } from "@/hooks/useOptimization";
import { fmtMoneyShort } from "@/lib/format";
import { MetricsResponse } from "@/lib/types";

function useHour(): number {
  const [hour, setHour] = useState(() => new Date().getHours());
  useEffect(() => {
    const timer = setInterval(() => setHour(new Date().getHours()), 60_000);
    return () => clearInterval(timer);
  }, []);
  return hour;
}

export default function TodayCard({ metrics }: { metrics: MetricsResponse }) {
  const hour = useHour();
  const { money, isLoading: moneyLoading } = useMoney();
  const { data: forecast } = useForecast();

  const ready = forecast?.ready ? forecast : null;
  const tomorrow = ready ? tomorrowOf(ready.days) : null;
  const kind = useMemo(() => {
    const qual = tomorrow ? lockedQual(tomorrow.date, tomorrow.qual) : null;
    return dayKind(qual, tomorrow?.kwh ?? null, ready?.avg30_kwh ?? null);
  }, [tomorrow, ready?.avg30_kwh]);
  const suggestion = buildSuggestions({ metrics, kind, tier: money?.tier, hour })[0];
  const saved = money?.today.saved;

  return (
    <Card pad="p-4 sm:p-5" aria-labelledby="today-actions">
      <h2 className="text-sm font-bold text-zinc-100" id="today-actions">
        Today
      </h2>
      <ul className="mt-3 divide-y divide-white/5">
        <li>
          <Link className="flex items-center gap-3 py-2.5 transition hover:text-zinc-50" href="/money">
            <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-good/10 text-good ring-1 ring-inset ring-good/30">
              <i className="fa-solid fa-coins" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[13px] font-semibold text-zinc-100">
                {moneyLoading && saved == null
                  ? "Savings updating…"
                  : saved == null
                    ? "Today's savings"
                    : `Saved today ~${fmtMoneyShort(saved)}`}
              </span>
              <span className="mt-0.5 block text-[11px] text-zinc-400">Open Money</span>
            </span>
            <i className="fa-solid fa-chevron-right text-[10px] text-zinc-500" />
          </Link>
        </li>
        <li>
          <Link className="flex items-center gap-3 py-2.5 transition hover:text-zinc-50" href="/optimization">
            <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-load/10 text-load ring-1 ring-inset ring-load/30">
              <i className={`fa-solid ${suggestion?.icon ?? "fa-lightbulb"}`} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[13px] font-semibold leading-snug text-zinc-100">
                {suggestion ? suggestion.title : "See what to do today"}
              </span>
              <span className="mt-0.5 block text-[11px] text-zinc-400">
                {suggestion ? suggestion.when : "Open Optimization"}
              </span>
            </span>
            <i className="fa-solid fa-chevron-right text-[10px] text-zinc-500" />
          </Link>
        </li>
      </ul>
    </Card>
  );
}
