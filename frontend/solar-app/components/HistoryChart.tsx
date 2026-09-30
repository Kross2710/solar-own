"use client";

import { useEffect, useRef } from "react";
import type ApexCharts from "apexcharts";
import type { ApexOptions } from "apexcharts";

export type Range = "Day" | "Month" | "Year";

export interface ChartBarData {
  label: string;
  solar: number;
  grid: number;
}

interface HistoryChartProps {
  range: Range;
  onRangeChange: (range: Range) => void;
  data: ChartBarData[];
}

export default function HistoryChart({ range, onRangeChange, data }: HistoryChartProps) {
  const chartElement = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<ApexCharts | null>(null);

  useEffect(() => {
    const element = chartElement.current;
    if (!element) return;

    let cancelled = false;

    chartInstance.current?.destroy();
    chartInstance.current = null;

    const renderChart = async () => {
      const { default: ApexChartsConstructor } = await import("apexcharts");
      if (cancelled) return;

      const options: ApexOptions = {
        chart: {
          type: "bar",
          height: 230,
          stacked: true,
          background: "transparent",
          toolbar: { show: false },
          parentHeightOffset: 0,
          animations: {
            enabled: true,
            easing: "easeinout",
            speed: 450,
          },
        },
        series: [
          {
            name: "Grid bought",
            data: data.map((item) => item.grid),
          },
          {
            name: "Solar",
            data: data.map((item) => item.solar),
          },
        ],
        colors: ["#446078", "#ffc76b"],
        plotOptions: {
          bar: {
            horizontal: false,
            columnWidth: range === "Day" ? "48%" : "42%",
            borderRadius: 4,
            borderRadiusApplication: "end",
          },
        },
        dataLabels: { enabled: false },
        stroke: {
          show: true,
          width: 1,
          colors: ["transparent"],
        },
        fill: {
          type: "gradient",
          opacity: 1,
          gradient: {
            shade: "dark",
            type: "vertical",
            shadeIntensity: 0.25,
            opacityFrom: 1,
            opacityTo: 0.72,
            stops: [0, 100],
          },
        },
        grid: {
          borderColor: "rgba(255, 255, 255, 0.06)",
          strokeDashArray: 3,
          xaxis: { lines: { show: false } },
          padding: {
            top: 4,
            right: 4,
            bottom: 0,
            left: 2,
          },
        },
        xaxis: {
          categories: data.map((item) => item.label),
          axisBorder: { show: false },
          axisTicks: { show: false },
          labels: {
            trim: false,
            rotate: 0,
            style: {
              colors: data.map(() => "#707a8e"),
              fontSize: "10px",
            },
          },
        },
        yaxis: {
          min: 0,
          forceNiceScale: true,
          tickAmount: 3,
          labels: {
            formatter: (value: number) => Math.round(value).toString(),
            style: {
              colors: ["#707a8e"],
              fontSize: "11px",
            },
          },
        },
        legend: {
          show: true,
          position: "bottom",
          horizontalAlign: "center",
          fontSize: "11px",
          labels: { colors: "#9aa3b5" },
          itemMargin: { horizontal: 10, vertical: 2 },
        },
        tooltip: {
          theme: "dark",
          shared: true,
          intersect: false,
          y: {
            formatter: (value: number) => `${value.toFixed(1)} kWh`,
          },
        },
        noData: {
          text: "No history data",
          align: "center",
          verticalAlign: "middle",
          style: {
            color: "#707a8e",
            fontSize: "12px",
          },
        },
      };

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
  }, [data, range]);

  return (
    <>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-zinc-100">Daily generation</h2>
        <div className="flex rounded-full border border-white/10 bg-white/[0.04] p-1">
          {(["Day", "Month", "Year"] as Range[]).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => onRangeChange(item)}
              className={`rounded-full px-4 py-1.5 text-xs font-semibold transition ${
                range === item
                  ? "bg-white/15 text-zinc-100 shadow-sm"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 min-h-[230px] w-full" ref={chartElement} />
    </>
  );
}