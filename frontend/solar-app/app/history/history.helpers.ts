import { DailyResponse, SummaryResponse } from "@/lib/types";
import { ChartBarData } from "@/components/HistoryChart";
import { MONTH_NAMES, parseDateMonth } from "@/lib/format";

export function formatDayBars(dailyData?: DailyResponse[]): ChartBarData[] {
  const slice = (dailyData ?? []).slice(-14);
  return slice.map((item, index) => {
    const dayOfMonth = parseInt((item.day ?? "").split("-")[2] ?? "0", 10).toString();
    return {
      label: index % 2 === 0 ? dayOfMonth : "",
      solar: Number((item.kwh ?? 0).toFixed(1)),
      grid: Number((item.buy ?? 0).toFixed(1)),
    };
  });
}

export function formatMonthBars(summaryData?: SummaryResponse): ChartBarData[] {
  return (summaryData?.monthly ?? []).map((item) => {
    const monthIndex = parseInt(item.month.split("-")[1], 10) - 1;
    return {
      label: MONTH_NAMES[monthIndex] ?? item.month,
      solar: Number(item.kwh.toFixed(1)),
      grid: Number(item.buy.toFixed(1)),
    };
  });
}

export function formatYearBars(summaryData?: SummaryResponse): ChartBarData[] {
  return (summaryData?.yearly ?? []).map((item) => ({
    label: item.year,
    solar: Number(item.kwh.toFixed(1)),
    grid: Number(item.buy.toFixed(1)),
  }));
}

export function calculateSelfPoweredDays(dailyData?: DailyResponse[]): number[] {
  return (dailyData?.slice(1) ?? []).map((item) => {
    if (item.cons && item.buy) {
      return Math.round(((item.cons - item.buy) / item.cons) * 100);
    }
    return 0;
  });
}

export function getSelfPoweredDateRange(dailyData?: DailyResponse[]): string[] {
  const dates = (dailyData?.slice(1) ?? []).map((item) => item.day ?? "");
  if (!dates.length) return ["", ""];
  return [parseDateMonth(dates[0] ?? ""), parseDateMonth(dates[dates.length - 1] ?? "")];
}