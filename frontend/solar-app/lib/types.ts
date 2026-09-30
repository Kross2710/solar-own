export interface MetricsResponse {
  status?: string;
  source?: string;
  pv_power_w?: number;
  load_power_w?: number;
  grid_power_w?: number;
  battery_power_w?: number;
  battery_soc?: number;
  today_consumption_kwh?: number;
  today_energy_kwh?: number;
  today_buy_kwh?: number;
  total_energy_kwh?: number;
  battery_capacity_kwh?: number | null;
  battery_reserve_percent?: number | null;
  poll_interval_seconds?: number;
  error?: string;
}

export interface DailyResponse {
  day?: string;
  kwh?: number;
  cons?: number;
  buy?: number;
}

export interface MonthlyItem {
  month: string;
  kwh: number;
  cons: number;
  buy: number;
  days: number;
  saved: number;
}

export interface YearlyItem {
  year: string;
  kwh: number;
  cons: number;
  buy: number;
  days: number;
  saved: number;
}

export interface SummaryResponse {
  currency: string;
  monthly: MonthlyItem[];
  yearly: YearlyItem[];
  records: {
    best_day: { day: string; kwh: number };
    best_self_day: { day: string; pct: number };
    peak_month: { month: string; kwh: number };
    streak: { days: number; start: string; end: string };
  };
}