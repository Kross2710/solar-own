"use client";

import { useEffect, useRef } from "react";
import type ApexCharts from "apexcharts";
import type { ApexOptions } from "apexcharts";
import { cycleMonthLabel, cycleMonthYearLabel } from "@/app/money/money.helpers";
import { fmtMoney } from "@/lib/format";
import { MoneyEvnHistoryItem } from "@/lib/types/money";

const BEFORE_SOLAR = "#fb8a95";
const WITH_SOLAR = "#34d399";

function axisMoney(value: number): string {
  if (value >= 1_000_000) return `${Math.round(value / 100_000) / 10}M`;
  if (value >= 1000) return `${Math.round(value / 1000)}k`;
  return String(Math.round(value));
}

interface BillHistoryChartProps {
  history: MoneyEvnHistoryItem[];
  solarStart: string | null;
}

export default function BillHistoryChart({ history, solarStart }: BillHistoryChartProps) {
  const chartElement = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<ApexCharts | null>(null);

  useEffect(() => {
    const element = chartElement.current;
    if (!element) return;

    let cancelled = false;
    const solarCycle = solarStart?.slice(0, 7) ?? null;
    const hasSolar = (cycle: string) => solarCycle != null && cycle >= solarCycle;

    const renderChart = async () => {
      const { default: ApexChartsConstructor } = await import("apexcharts");
      if (cancelled) return;

      const options: ApexOptions = {
        chart: {
          type: "bar",
          height: 180,
          background: "transparent",
          toolbar: { show: false },
          parentHeightOffset: 0,
          animations: { enabled: true, speed: 450 },
        },
        series: [{ name: "EVN bill", data: history.map((item) => item.amount) }],
        colors: history.map((item) => (hasSolar(item.cycle) ? WITH_SOLAR : BEFORE_SOLAR)),
        plotOptions: {
          bar: {
            distributed: true,
            columnWidth: "58%",
            borderRadius: 3,
            borderRadiusApplication: "end",
          },
        },
        legend: { show: false },
        dataLabels: { enabled: false },
        fill: { opacity: 0.85 },
        grid: {
          borderColor: "rgba(255, 255, 255, 0.06)",
          strokeDashArray: 3,
          xaxis: { lines: { show: false } },
          padding: { top: 0, right: 2, bottom: 0, left: 0 },
        },
        xaxis: {
          categories: history.map((item) => item.cycle),
          axisBorder: { show: false },
          axisTicks: { show: false },
          labels: {
            rotate: 0,
            hideOverlappingLabels: true,
            formatter: (value: string) => (value ? cycleMonthLabel(value) : ""),
            style: { colors: "#707a8e", fontSize: "10px" },
          },
          tooltip: { enabled: false },
        },
        yaxis: {
          min: 0,
          tickAmount: 3,
          labels: {
            formatter: axisMoney,
            style: { colors: ["#707a8e"], fontSize: "10px" },
          },
        },
        annotations: solarCycle && history.some((item) => item.cycle === solarCycle)
          ? {
              xaxis: [
                {
                  x: solarCycle,
                  borderColor: "rgba(255, 199, 107, 0.7)",
                  strokeDashArray: 3,
                  label: {
                    text: "Solar",
                    orientation: "horizontal",
                    offsetY: -4,
                    borderWidth: 0,
                    style: { background: "transparent", color: "#ffc76b", fontSize: "10px", fontWeight: 700 },
                  },
                },
              ],
            }
          : undefined,
        tooltip: {
          theme: "dark",
          x: { formatter: (_value: number, opts) => cycleMonthYearLabel(history[opts?.dataPointIndex ?? 0].cycle) },
          y: { formatter: (value: number) => fmtMoney(value), title: { formatter: () => "" } },
        },
      };

      chartInstance.current?.destroy();
      const chart = new ApexChartsConstructor(element, options);
      chartInstance.current = chart;
      await chart.render();
    };

    void renderChart();

    return () => {
      cancelled = true;
      chartInstance.current?.destroy();
      chartInstance.current = null;
    };
  }, [history, solarStart]);

  return <div className="min-h-[180px] w-full" ref={chartElement} />;
}
