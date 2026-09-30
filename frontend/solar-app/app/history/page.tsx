"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import DashboardShell from "@/components/DashboardShell";
import HistoryChart, { Range, ChartBarData } from "../../components/HistoryChart";
import HistoryStatGrid from "../../components/HistoryStatGrid";
import SelfPoweredCard from "../../components/SelfPoweredCard";

import { apiUrl, fetcher } from "@/lib/api";
import { formatDayBars, formatMonthBars, formatYearBars, getSelfPoweredDateRange, calculateSelfPoweredDays } from "./history.helpers";
import { parseDateMonthYear } from "@/lib/format";
import { DailyResponse, SummaryResponse } from "@/lib/types";

export default function HistoryPage() {
  const [range, setRange] = useState<Range>("Day");

  // Gọi đồng thời 2 API
  const {
    data: dailyData,
    error: dailyError,
    isLoading: dailyLoading,
  } = useSWR<DailyResponse[]>(apiUrl("/api/daily?days=31"), fetcher, {
    refreshInterval: 100000,
  });

  const {
    data: summaryData,
    error: summaryError,
    isLoading: summaryLoading,
  } = useSWR<SummaryResponse>(apiUrl("/api/summary"), fetcher, {
    refreshInterval: 50000,
  });

  const dayBars = useMemo(() => formatDayBars(dailyData), [dailyData]);
  const monthBars = useMemo(() => formatMonthBars(summaryData), [summaryData]);
  const yearBars = useMemo(() => formatYearBars(summaryData), [summaryData]);

  const selfPoweredDays = useMemo(() => calculateSelfPoweredDays(dailyData), [dailyData]);
  const selfPoweredDates = useMemo(() => getSelfPoweredDateRange(dailyData), [dailyData]);

  const avgSelfPowered = useMemo(() => {
    if (!selfPoweredDays.length) return 0;
    return Math.round(selfPoweredDays.reduce((sum, v) => sum + v, 0) / selfPoweredDays.length);
  }, [selfPoweredDays]);

  // Chọn thanh bar hiển thị theo tab
  const activeBars = range === "Day" ? dayBars : range === "Month" ? monthBars : yearBars;

  // Lấy dữ liệu tháng hiện tại (phần tử cuối cùng trong mảng monthly)
  const currentMonth = summaryData?.monthly?.[summaryData.monthly.length - 1];
  const totalSolarThisMonth = currentMonth ? Math.round(currentMonth.kwh) : 0;
  // Solar - Grid = used from solar
  const totalUsedFromSolar = currentMonth ? Math.round(currentMonth.cons - currentMonth.buy) : 0;
  const totalSavedThisMonth = currentMonth
    ? `${(currentMonth.saved / 1000).toFixed(0)}k`
    : "0k";
  // Lấy thông tin năm hiện tại
  const currentYear = summaryData?.yearly?.[summaryData.yearly.length - 1];

  if (dailyLoading || summaryLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#04060c] font-sans text-zinc-400">
        Connecting to Solar...
      </div>
    );
  }

  if (dailyError || summaryError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#04060c] font-sans text-red-400">
        Can&apos;t get data from Backend
      </div>
    );
  }

  const todaykWh = dailyData?.slice(-1)[0]?.kwh ?? 0;
  const past30Dayskwh = dailyData?.[0]?.kwh ?? 0;

  // 2. Luôn lấy past30Dayskwh làm mốc chuẩn
  const diff = todaykWh - past30Dayskwh;
  const percent = Math.abs((diff / past30Dayskwh) * 100).toFixed(1);

  let compare = "";
  if (diff > 0) {
    compare = `up ${percent}% vs the last 30 days`;
  } else if (diff < 0) {
    compare = `down ${percent}% vs the last 30 days`;
  } else {
    compare = `equal to 30 days ago`;
  }

  // 4 card thống kê lấy trực tiếp từ API Summary
  const statItems = [
    {
      label: "Today",
      value: `${todaykWh} kWh`,
      detail: `${compare}`,
    },
    {
      label: "Best day",
      value: `${summaryData?.records?.best_day?.kwh ?? 0} kWh`,
      detail: summaryData?.records?.best_day?.day
        ? parseDateMonthYear(summaryData.records.best_day.day)
        : "--",
    },
    {
      label: "This month",
      value: `${totalSolarThisMonth} kWh`,
      detail: `Saved ${currentMonth?.saved?.toLocaleString("vi-VN") ?? 0} đ`,
    },
    {
      label: `Total · ${currentYear?.days ?? 0} days`,
      value: `${currentYear?.kwh?.toFixed(0) ?? 0} kWh`,
      detail: `Saved ${currentYear?.saved?.toLocaleString("vi-VN") ?? 0} đ`,
    },
  ];

  return (
    <DashboardShell status="live" source="">
      <section className="text-center" aria-labelledby="month-generation">
        <p className="text-xs font-bold uppercase tracking-[0.28em] text-zinc-400" id="month-generation">
          This Month
        </p>
        <p className="mt-2 bg-gradient-to-b from-white to-[#ffc76b] bg-clip-text text-[clamp(52px,14vw,68px)] font-extralight leading-none tracking-[-0.055em] text-transparent tabular-nums">
          {totalSolarThisMonth} kWh
        </p>
        <p className="mt-2 text-[13px] text-zinc-300">
          saved <strong className="text-emerald-400">{totalSavedThisMonth}</strong> (used {totalUsedFromSolar} kWh)
          {/* <span className="text-zinc-500"> · </span>
          home self-powered 72% */}
        </p>
      </section>

      <section className="rounded-[22px] border border-white/10 border-t-amber-300/20 bg-[#0a0e18]/90 p-3 shadow-2xl backdrop-blur-xl sm:p-4">
        <HistoryChart range={range} onRangeChange={setRange} data={activeBars} />
        <HistoryStatGrid items={statItems} />
      </section>

      <SelfPoweredCard selfPoweredDays={selfPoweredDays} selfPoweredDates={selfPoweredDates} avgSelfPowered={avgSelfPowered} />
    </DashboardShell>
  );
}