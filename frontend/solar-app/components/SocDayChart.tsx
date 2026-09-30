"use client";

import { useEffect, useRef } from "react";

interface SocDayChartProps {
  // Dữ liệu theo giờ: mảng [timestamp, % pin]
  data?: [number, number][];
  reservePercent?: number; // Mức pin dự phòng (mặc định 20%)
}

export default function SocDayChart({ data, reservePercent = 20 }: SocDayChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<any>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    // Dữ liệu mẫu 24h hôm nay nếu chưa truyền data từ API
    const generateDefaultData = (): [number, number][] => {
      const now = new Date();
      const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0).getTime();
      const currentHour = now.getHours();
      
      const mockPoints: [number, number][] = [];
      let soc = 65;
      for (let h = 0; h <= currentHour; h++) {
        const time = startOfDay + h * 3600 * 1000;
        // Giả lập: ban đêm xả, trưa nắng sạc đầy, chiều xả nhẹ
        if (h < 6) soc = Math.max(30, soc - 4);
        else if (h < 13) soc = Math.min(98, soc + 10);
        else soc = Math.max(35, soc - 5);

        mockPoints.push([time, Math.round(soc)]);
      }
      return mockPoints;
    };

    const seriesData = data && data.length > 0 ? data : generateDefaultData();

    // Import động ApexCharts ở Client-side để tránh lỗi 'window is not defined'
    import("apexcharts").then(({ default: ApexCharts }) => {
      if (chartInstance.current) {
        chartInstance.current.destroy();
      }

      // Tạo đường baseline pin dự phòng (nét đứt)
      const reserveData = seriesData.map(([time]) => [time, reservePercent]);

      const options: any = {
        chart: {
          id: "socDayChart",
          type: "area",
          height: 195,
          background: "transparent",
          toolbar: { show: false },
          animations: { enabled: true, easing: "easeinout", speed: 600 },
          parentHeightOffset: 0,
        },
        dataLabels: {
          enabled: false, // Ẩn hoàn toàn dãy số hiển thị cho mức dự trữ 20% và số pin
        },
        theme: { mode: "dark" },
        stroke: {
          curve: "smooth",
          width: [2.5, 1.5],
          dashArray: [0, 4], // Đường 1 nét liền, đường 2 nét đứt
        },
        colors: ["#b8a6ff", "rgba(255, 255, 255, 0.35)"], // #b8a6ff là màu pin chuẩn Aurora
        fill: {
          type: ["gradient", "solid"],
          gradient: {
            shadeIntensity: 1,
            opacityFrom: 0.35,
            opacityTo: 0.05,
            stops: [0, 90, 100],
          },
        },
        series: [
          { name: "Mức pin (SOC)", data: seriesData },
          { name: "Mức dự phòng", data: reserveData },
        ],
        xaxis: {
          type: "datetime",
          labels: {
            style: { colors: "#707a8e", fontSize: "11px" },
            datetimeUTC: false,
            format: "HH:mm",
          },
          axisBorder: { show: false },
          axisTicks: { show: false },
        },
        yaxis: {
          min: 0,
          max: 100,
          tickAmount: 4,
          labels: {
            style: { colors: "#707a8e", fontSize: "11px" },
            formatter: (v: number) => `${Math.round(v)}%`,
          },
        },
        grid: {
          borderColor: "rgba(255, 255, 255, 0.06)",
          strokeDashArray: 3,
          xaxis: { lines: { show: false } },
          padding: {
            top: -6,
            right: 8,
            bottom: 4,
            left: 0,
          },
        },
        markers: {
          size: 0,
          hover: { size: 5 },
        },
        tooltip: {
          theme: "dark",
          x: { format: "HH:mm" },
          y: {
            formatter: (v: number, { seriesIndex }: any) =>
              `${seriesIndex === 1 ? "Dự phòng" : "Pin"}: ${Math.round(v)}%`,
          },
        },
        legend: {
          show: false,
        },
      };

      if (!chartRef.current) return;
      chartInstance.current = new ApexCharts(chartRef.current, options);
      chartInstance.current.render();
    });

    // Cleanup khi component bị hủy
    return () => {
      if (chartInstance.current) {
        chartInstance.current.destroy();
        chartInstance.current = null;
      }
    };
  }, [data, reservePercent]);

  return <div ref={chartRef} className="w-full" />;
}