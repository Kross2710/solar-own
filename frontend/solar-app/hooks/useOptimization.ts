import useSWR from "swr";
import { apiUrl, fetcher } from "@/lib/api";
import { MetricsResponse } from "@/lib/types";
import { CurtailmentResponse, ForecastResponse, HourlyResponse } from "@/lib/types/optimization";

const MINUTE = 60 * 1000;
// The server may still be fetching weather / training: retry quickly until ready.
const FORECAST_RETRY_MS = 30 * 1000;
const FORECAST_REFRESH_MS = 3 * 60 * MINUTE;

export function useForecast() {
  return useSWR<ForecastResponse>(apiUrl("/api/forecast"), fetcher, {
    refreshInterval: (latest) => (latest?.ready ? FORECAST_REFRESH_MS : FORECAST_RETRY_MS),
  });
}

export function useHourly() {
  return useSWR<HourlyResponse>(apiUrl("/api/hourly"), fetcher, { refreshInterval: 30 * MINUTE });
}

export function useCurtailment() {
  return useSWR<CurtailmentResponse>(apiUrl("/api/curtailment"), fetcher, { refreshInterval: 5 * MINUTE });
}

export function useMetrics() {
  return useSWR<MetricsResponse>(apiUrl("/api/metrics"), fetcher, { refreshInterval: MINUTE });
}
