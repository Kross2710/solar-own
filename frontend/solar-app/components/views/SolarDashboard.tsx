"use client";

import useSWR from "swr";
import DashboardPage from "../DashboardPage";
import OverviewTimeChart, {
  PowerHistoryPoint,
} from "../OverviewTimeChart";
import Card from "@/components/Card";
import LivingHouse from "@/components/house/LivingHouse";
import { useHouseScene } from "@/components/house/useHouseScene";
import TodayCard from "@/components/overview/TodayCard";
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/useMediaQuery";
import { useState } from "react";

import { apiUrl, fetcher } from "@/lib/api";
import { COLORS } from "@/lib/colors";
import { DailyResponse, MetricsResponse } from "@/lib/types";

type PowerTab = "Power" | "Battery";

function DetailsButton({
  open,
  onClick,
}: {
  open: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className="mx-auto flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] px-4 py-1.5 text-xs font-semibold text-zinc-400 transition hover:border-white/20 hover:text-zinc-100"
      type="button"
      aria-expanded={open}
      onClick={onClick}
    >
      {open ? "Hide details" : "See details"}
      <span className={`text-[9px] transition-transform ${open ? "rotate-180" : ""}`}>▼</span>
    </button>
  );
}

export default function Dashboard() {
  const [powerTab, setPowerTab] = useState<PowerTab>("Power");
  const [detailOpen, setDetailOpen] = useState(false);
  // Desktop has room for the chart, so it is always shown there.
  const isDesktop = useMediaQuery(DESKTOP_QUERY);

  const { data, error, isLoading } = useSWR<MetricsResponse>(
    apiUrl("/api/metrics"),
    fetcher,
    {
      refreshInterval: 3000,
      revalidateOnFocus: true,
      dedupingInterval: 1000,
    }
  );

  const { data: historyData } = useSWR<PowerHistoryPoint[]>(
    apiUrl("/api/history?hours=24"),
    fetcher,
    {
      refreshInterval: 30000,
      revalidateOnFocus: true,
      dedupingInterval: 5000,
    }
  );

  const { data: dailyData } = useSWR<DailyResponse[]>(apiUrl("/api/daily?days=31"), fetcher, {
    refreshInterval: 10 * 60 * 1000,
  });

  if (isLoading && !data) {
    return (
      <DashboardPage status="connecting">
        <OverviewSkeleton />
      </DashboardPage>
    );
  }

  if (error || !data) {
    return (
      <DashboardPage status="error">
        <Card accent="warn" pad="p-6" className="text-center" role="alert">
          <p className="text-sm font-semibold text-grid-in">Can&apos;t get data from the backend</p>
          <p className="mt-1 text-[12px] text-zinc-400">The rest of the app stays available from the tabs below.</p>
        </Card>
      </DashboardPage>
    );
  }

  // Chuyển đổi chỉ số hiển thị
  const battSoc = data?.battery_soc ?? 0;
  const today_consumption_kwh = data?.today_consumption_kwh ?? 0;
  const today_energy_kwh = data?.today_energy_kwh ?? 0;
  const today_buy_kwh = data?.today_buy_kwh ?? 0;

  const solar_battery_consumption = today_consumption_kwh - today_buy_kwh;
  const solar_battery_consumption_percent = today_consumption_kwh ? (solar_battery_consumption / today_consumption_kwh) * 100 : 0;
  const grid_consumption_percent = today_consumption_kwh ? (today_buy_kwh / today_consumption_kwh) * 100 : 0;
  const solarUsagePercent = Math.min(100, Math.max(0, solar_battery_consumption_percent));
  const reservePercent = data?.battery_reserve_percent ?? 20;
  const selfPowered = selfPoweredBaseline(dailyData);

  return (
    <DashboardPage status={data?.status} source={data?.source} updatedAt={data?.timestamp}>
      {/* Stale bar cảnh báo */}
      <div
        className="flex items-center gap-[9px] rounded-xl border border-grid-in/50 bg-grid-in/14 px-3.5 py-[9px] text-[13px] font-semibold text-grid-in"
        id="staleBar"
        hidden={!data?.error}
      >
        <span className="shrink-0 text-base">
          <i className="fa-solid fa-triangle-exclamation" />
        </span>
        <span id="staleText">{data?.error}</span>
      </div>

      {/* Desktop: the house spans two rows beside Today and usage; the chart runs full width below. */}
      <div className="grid gap-7 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <Card pad="px-3 py-3 sm:px-6 sm:py-6" className="xl:row-span-2 xl:flex xl:items-center">
          <HouseScene metrics={data} />
        </Card>
        <TodayCard metrics={data} />
        <Card pad="p-6 sm:p-8" id="usageCard">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-sm font-bold text-zinc-100">Today&apos;s usage</h2>
            <span className="text-[11px] tabular-nums text-zinc-400" id="usagePvGen">
              Generated {today_energy_kwh} kWh
            </span>
          </div>

          <div className="mt-5 grid grid-cols-[minmax(0,1fr)_7rem_minmax(0,1fr)] items-center gap-2 sm:grid-cols-[1fr_8rem_1fr] sm:gap-4">
            <div className="flex min-w-0 flex-col">
              <div className="text-[11px] text-zinc-400">Solar + battery</div>
              <div className="mt-1 whitespace-nowrap text-xl font-light tracking-tight tabular-nums text-pv">
                <span id="usagePvKwh">{solar_battery_consumption.toFixed(1)}</span>
                <small className="ml-1 text-[10px] font-semibold tracking-normal text-zinc-400">kWh</small>
              </div>
              <div className="mt-0.5 text-sm font-bold tabular-nums text-pv" id="usagePvPct">
                {solarUsagePercent.toFixed(0)}%
              </div>
            </div>

            <div className="relative mx-auto size-28 rounded-full p-3 sm:size-32">
              <div
                className="absolute inset-0 rounded-full"
                style={{
                  background: `conic-gradient(${COLORS.pv} 0 ${solarUsagePercent}%, ${COLORS.load} ${solarUsagePercent}% 100%)`,
                }}
                aria-hidden="true"
              />
              <div className="absolute inset-3 rounded-full border border-white/5 bg-card" />
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
                <span className="text-lg font-light tracking-tight tabular-nums text-zinc-100" id="usageTotalKwh">
                  {today_consumption_kwh}
                </span>
                <small className="text-[9px] text-zinc-400">kWh used</small>
              </div>
            </div>

            <div className="flex min-w-0 flex-col text-right">
              <div className="text-[11px] text-zinc-400">Grid</div>
              <div className="mt-1 whitespace-nowrap text-xl font-light tracking-tight tabular-nums text-load">
                <span id="usageGridKwh">{today_buy_kwh}</span>
                <small className="ml-1 text-[10px] font-semibold tracking-normal text-zinc-400">kWh</small>
              </div>
              <div className="mt-0.5 text-sm font-bold tabular-nums text-load" id="usageGridPct">
                {grid_consumption_percent.toFixed(0)}%
              </div>
            </div>
          </div>
          {selfPowered && (
            <p className="mt-4 text-center text-[12px] tabular-nums text-zinc-400">
              {selfPowered.yesterday != null && (
                <>
                  Yesterday <strong className="font-semibold text-zinc-200">{selfPowered.yesterday}%</strong>
                  <span className="text-zinc-600"> · </span>
                </>
              )}
              30-day avg <strong className="font-semibold text-zinc-200">{selfPowered.avg}%</strong>
            </p>
          )}
          <p className="mt-2 text-center text-[11px] leading-snug text-zinc-500">
            Solar + battery is energy not bought from the grid (estimate).
          </p>
        </Card>

        {!isDesktop && (
          <div className="mt-4">
            <DetailsButton
              open={detailOpen}
              onClick={() => setDetailOpen((value) => !value)}
            />
          </div>
        )}

        {(detailOpen || isDesktop) && (
          <Card accent="pv" className="xl:col-span-2">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-bold text-zinc-100">
                  {powerTab === "Power" ? "Power over time" : "Battery level today"}
                </h2>
                {powerTab === "Battery" && (
                  <span className="mt-1 block text-[11px] font-semibold tabular-nums text-batt">
                    Current SOC · {battSoc}%
                  </span>
                )}
              </div>
              <div className="flex rounded-full bg-white/[0.04] p-1">
                {(["Power", "Battery"] as PowerTab[]).map((item) => (
                  <button
                    className={`rounded-full px-4 py-1.5 text-xs font-semibold transition ${powerTab === item
                      ? "bg-white/15 text-zinc-100"
                      : "text-zinc-500"
                      }`}
                    type="button"
                    key={item}
                    onClick={() => setPowerTab(item)}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-4 overflow-hidden rounded-xl border border-white/[0.06] bg-black/10 px-1 pt-2">
              <OverviewTimeChart
                data={historyData ?? []}
                mode={powerTab}
                reservePercent={reservePercent}
              />
            </div>
          </Card>
        )}
      </div>
    </DashboardPage>
  );
}

function HouseScene({ metrics }: { metrics: MetricsResponse }) {
  return <LivingHouse scene={useHouseScene(metrics)} />;
}

function selfPoweredPct(day: DailyResponse): number | null {
  if (!day.cons || day.buy == null) return null;
  return Math.round(((day.cons - day.buy) / day.cons) * 100);
}

// The last row is today (still running), so it is left out of the comparison.
function selfPoweredBaseline(daily: DailyResponse[] | undefined) {
  if (!daily || daily.length < 2) return null;
  const past = daily.slice(0, -1).map(selfPoweredPct).filter((pct): pct is number => pct != null);
  if (!past.length) return null;
  return {
    yesterday: selfPoweredPct(daily[daily.length - 2]),
    avg: Math.round(past.reduce((sum, pct) => sum + pct, 0) / past.length),
  };
}

function OverviewSkeleton() {
  return (
    <div className="flex flex-col gap-7" aria-hidden="true">
      <Card pad="" className="h-72 animate-pulse" />
      <Card pad="" className="h-64 animate-pulse" />
      <Card pad="" className="h-44 animate-pulse" />
    </div>
  );
}