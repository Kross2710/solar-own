"use client";

import { useEffect, useRef } from "react";
import type ApexCharts from "apexcharts";
import type { ApexOptions } from "apexcharts";

export type OverviewChartMode = "Power" | "Battery";

export interface PowerHistoryPoint {
  ts: string;
  pv: number | null;
  load: number | null;
  grid: number | null;
  soc: number | null;
}

interface OverviewTimeChartProps {
  data: PowerHistoryPoint[];
  mode: OverviewChartMode;
  reservePercent?: number;
}

export default function OverviewTimeChart({
  data,
  mode,
  reservePercent = 20,
}: OverviewTimeChartProps) {
  const chartElement = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<ApexCharts | null>(null);

  useEffect(() => {
    const element = chartElement.current;
    if (!element) return;

    let cancelled = false;
    chartInstance.current?.destroy();
    chartInstance.current = null;

    const points = data
      .map((point) => ({
        ...point,
        time: new Date(point.ts).getTime(),
      }))
      .filter((point) => Number.isFinite(point.time));

    const renderChart = async () => {
      const { default: ApexChartsConstructor } = await import("apexcharts");
      if (cancelled) return;

      const powerSeries = [
        {
          name: "Solar",
          data: points.map((point) => ({ x: point.time, y: point.pv })),
        },
        {
          name: "Home load",
          data: points.map((point) => ({ x: point.time, y: point.load })),
        },
      ];

      const batterySeries = [
        {
          name: "Battery SOC",
          data: points.map((point) => ({ x: point.time, y: point.soc })),
        },
        {
          name: "Reserve",
          data: points.map((point) => ({ x: point.time, y: reservePercent })),
        },
      ];

      const isBattery = mode === "Battery";
      const options: ApexOptions = {
        chart: {
          type: "area",
          height: 230,
          background: "transparent",
          toolbar: { show: false },
          zoom: { enabled: false },
          parentHeightOffset: 0,
          animations: {
            enabled: true,
            easing: "easeinout",
            speed: 450,
          },
        },
        series: isBattery ? batterySeries : powerSeries,
        colors: isBattery
          ? ["#b8a6ff", "rgba(255,255,255,0.38)"]
          : ["#ffc76b", "#7dd3fc"],
        dataLabels: { enabled: false },
        stroke: {
          curve: "smooth",
          width: isBattery ? [2.5, 1.5] : [2.5, 2],
          dashArray: isBattery ? [0, 5] : [0, 0],
        },
        fill: {
          type: "gradient",
          gradient: {
            shade: "dark",
            type: "vertical",
            shadeIntensity: 0.2,
            opacityFrom: isBattery ? 0.34 : 0.28,
            opacityTo: 0.02,
            stops: [0, 90, 100],
          },
        },
        markers: {
          size: 0,
          hover: { size: 4 },
        },
        grid: {
          borderColor: "rgba(255,255,255,0.06)",
          strokeDashArray: 3,
          xaxis: { lines: { show: false } },
          padding: { top: 2, right: 8, bottom: 2, left: 4 },
        },
        xaxis: {
          type: "datetime",
          axisBorder: { show: false },
          axisTicks: { show: false },
          labels: {
            datetimeUTC: false,
            format: "HH:mm",
            style: {
              colors: "#707a8e",
              fontSize: "10px",
            },
          },
        },
        yaxis: isBattery
          ? {
              min: 0,
              max: 100,
              tickAmount: 4,
              labels: {
                formatter: (value: number) => `${Math.round(value)}%`,
                style: { colors: ["#707a8e"], fontSize: "10px" },
              },
            }
          : {
              min: 0,
              forceNiceScale: true,
              tickAmount: 4,
              labels: {
                formatter: (value: number) =>
                  value >= 1000
                    ? `${(value / 1000).toFixed(1)}kW`
                    : `${Math.round(value)}W`,
                style: { colors: ["#707a8e"], fontSize: "10px" },
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
          x: { format: "HH:mm" },
          y: {
            formatter: (value: number, context) => {
              if (isBattery) {
                return context?.seriesIndex === 1
                  ? `${Math.round(value)}% reserve`
                  : `${Math.round(value)}% SOC`;
              }
              return value >= 1000
                ? `${(value / 1000).toFixed(2)} kW`
                : `${Math.round(value)} W`;
            },
          },
        },
        noData: {
          text: "No history data",
          align: "center",
          verticalAlign: "middle",
          style: { color: "#707a8e", fontSize: "12px" },
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
  }, [data, mode, reservePercent]);

  return <div className="min-h-[230px] w-full" ref={chartElement} />;
}
