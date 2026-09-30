// Shapes of GET /api/forecast, /api/hourly and /api/curtailment.

// Day-quality class from the server's classifier. These are protocol values, not UI text.
export type ForecastQual = "ít" | "vừa" | "tốt";

export interface ForecastDay {
  date: string;                // "YYYY-MM-DD"
  kwh: number | null;
  lo?: number;
  hi?: number;
  wcode?: number | null;       // WMO weather code
  tmax?: number | null;
  tmin?: number | null;
  rain_prob?: number | null;
  qual?: ForecastQual;
  today: boolean;
}

export interface ForecastQuality {
  model: string;
  mae: number;
  rmse: number;
  mape: number;
  r2: number;
  n_train: number;
  weather_responsive: boolean;
  skill_vs_climatology: number | null;
}

export type ForecastResponse =
  | { ready: false; reason: string }
  | {
      ready: true;
      model: string;
      avg30_kwh: number | null;
      night_need_kwh: number | null;
      quality: ForecastQuality;
      days: ForecastDay[];
      updated_at: string | null;
    };

export interface HourlyPoint {
  hour: number;
  pv: number | null;
  load: number | null;
  grid: number | null;         // W, > 0 = buying
  n: number;
}

export interface HourlyResponse {
  hours: HourlyPoint[];
  marginal: number;            // đ/kWh
  currency: string;
}

export type CurtailmentResponse =
  | { supported: false }
  | {
      supported: true;
      currency: string;
      marginal: number;
      today: {
        lost_kwh: number | null;
        full_at: string | null; // "HH:MM" when the battery hit ~full
        actual_kwh: number | null;
        potential_kwh: number | null;
      };
      total30_kwh: number;
      days: number;
      recent: { day: string; lost_kwh: number }[];
    };
