"use client";

import useSWR from "swr";
import IsometricHouse from "../IsometricHouse";
import DashboardShell from "../DashboardShell";
import OverviewTimeChart, {
  PowerHistoryPoint,
} from "../OverviewTimeChart";
import { useState } from "react";

import { apiUrl, fetcher } from "@/lib/api";
import { MetricsResponse } from "@/lib/types";

const cardClass =
  "rounded-[22px] border border-white/10 bg-[#0a0e18]/90 shadow-2xl backdrop-blur-xl";

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

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#04060c] text-zinc-400 flex items-center justify-center font-sans">
        Connecting to Solar...
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#04060c] text-red-400 flex items-center justify-center font-sans">
        Can&apos;t get data from Backend
      </div>
    );
  }

  // Chuyển đổi chỉ số hiển thị
  const pvWatt = data?.pv_power_w ?? 0;
  const houseWatt = data?.load_power_w ?? 0;
  const gridWatt = data?.grid_power_w ?? 0;
  const battWatt = data?.battery_power_w ?? 0;
  const battSoc = data?.battery_soc ?? 0;
  const today_consumption_kwh = data?.today_consumption_kwh ?? 0;
  const today_energy_kwh = data?.today_energy_kwh ?? 0;
  const today_buy_kwh = data?.today_buy_kwh ?? 0;

  const solar_battery_consumption = today_consumption_kwh - today_buy_kwh;
  const solar_battery_consumption_percent = today_consumption_kwh ? (solar_battery_consumption / today_consumption_kwh) * 100 : 0;
  const grid_consumption_percent = today_consumption_kwh ? (today_buy_kwh / today_consumption_kwh) * 100 : 0;
  const solarUsagePercent = Math.min(100, Math.max(0, solar_battery_consumption_percent));
  // Manipulate DOM elements for dynamic updates (if needed)
  let solarState = "";
  if (pvWatt && pvWatt > 0) {
    solarState = "Generating";
  }
  if (pvWatt === 0) {
    solarState = "Idle";
  }
  if (pvWatt < houseWatt) {
    solarState = "Discharging";
  }
  if (battSoc == 100 && houseWatt - pvWatt < 100) {
    solarState = "Fully Charged";
  }

  return (
    <DashboardShell status={data?.status} source={data?.source}>
      {/* Stale bar cảnh báo */}
      <div className="stale" id="staleBar" hidden={!data?.error}>
        <span className="stale-ico">
          <i className="fa-solid fa-triangle-exclamation" />
        </span>
        <span className="stale-text" id="staleText">{data?.error}</span>
      </div>

      <section className="relative px-3 py-3 sm:px-8 sm:py-10 rounded-[22px] bg-[#0a0e18]/90 border border-white/10 backdrop-blur-xl shadow-2xl">
        <IsometricHouse
          pvWatt={(pvWatt)}
          houseWatt={houseWatt}
          battWatt={battWatt}
          gridWatt={gridWatt}
          battSoc={battSoc}
          solarState={solarState}
        />
      </section>
      <section
        className="rounded-[22px] border border-white/10 bg-[#0a0e18]/90 p-6 shadow-2xl backdrop-blur-xl sm:p-8"
        id="usageCard"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-bold text-zinc-100">Today&apos;s usage</h2>
          <span className="text-[11px] tabular-nums text-zinc-400" id="usagePvGen">
            Generated {today_energy_kwh} kWh
          </span>
        </div>

        <div className="mt-5 grid grid-cols-[minmax(0,1fr)_7rem_minmax(0,1fr)] items-center gap-2 sm:grid-cols-[1fr_8rem_1fr] sm:gap-4">
          <div className="flex min-w-0 flex-col">
            <div className="text-[11px] text-zinc-400">Solar + battery</div>
            <div className="mt-1 whitespace-nowrap text-xl font-light tracking-tight tabular-nums text-amber-200">
              <span id="usagePvKwh">{solar_battery_consumption.toFixed(1)}</span>
              <small className="ml-1 text-[10px] font-semibold tracking-normal text-zinc-400">kWh</small>
            </div>
            <div className="mt-0.5 text-sm font-bold tabular-nums text-amber-300" id="usagePvPct">
              {solarUsagePercent.toFixed(0)}%
            </div>
          </div>

          <div className="relative mx-auto size-28 rounded-full p-3 sm:size-32">
            <div
              className="absolute inset-0 rounded-full"
              style={{
                background: `conic-gradient(#ffc76b 0 ${solarUsagePercent}%, #7dd3fc ${solarUsagePercent}% 100%)`,
              }}
              aria-hidden="true"
            />
            <div className="absolute inset-3 rounded-full border border-white/5 bg-[#0a0e18]" />
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
              <span className="text-lg font-light tracking-tight tabular-nums text-zinc-100" id="usageTotalKwh">
                {today_consumption_kwh}
              </span>
              <small className="text-[9px] text-zinc-400">kWh used</small>
            </div>
          </div>

          <div className="flex min-w-0 flex-col text-right">
            <div className="text-[11px] text-zinc-400">Grid</div>
            <div className="mt-1 whitespace-nowrap text-xl font-light tracking-tight tabular-nums text-sky-200">
              <span id="usageGridKwh">{today_buy_kwh}</span>
              <small className="ml-1 text-[10px] font-semibold tracking-normal text-zinc-400">kWh</small>
            </div>
            <div className="mt-0.5 text-sm font-bold tabular-nums text-sky-300" id="usageGridPct">
              {grid_consumption_percent.toFixed(0)}%
            </div>
          </div>
        </div>
      </section>
      <div className="mt-4">
        <DetailsButton
          open={detailOpen}
          onClick={() => setDetailOpen((value) => !value)}
        />
      </div>

      {detailOpen && (
        <section className={`${cardClass} border-t-amber-300/20 p-3 sm:p-4`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-bold text-zinc-100">
                {powerTab === "Power" ? "Power over time" : "Battery level today"}
              </h2>
              {powerTab === "Battery" && (
                <span className="mt-1 block text-[11px] font-semibold tabular-nums text-purple-300">
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
              reservePercent={20}
            />
          </div>
        </section>
      )}

    </DashboardShell>
  );
}