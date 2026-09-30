import useSWR from "swr";
import { apiUrl, fetcher } from "@/lib/api";
import { MoneyResponse } from "@/lib/types/money";

const REFRESH_MS = 5 * 60 * 1000;

export function useMoney() {
  const { data, error, isLoading } = useSWR<MoneyResponse>(apiUrl("/api/money"), fetcher, {
    refreshInterval: REFRESH_MS,
  });

  return { money: data, error, isLoading };
}
