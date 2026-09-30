// Shape of GET /api/status (Settings sheet).

export interface SyncResult {
  started_at: string;
  finished_at?: string;
  seconds?: number;
  errors: string[];              // failed steps: sems_daily | samples | curtailment | prune
  sems_months?: number;
  samples_filled?: number;
  curtailment_days?: number;
}

export interface StatusResponse {
  source: string;
  live: string | null;
  history: { days: number; first_day: string | null; last_day: string | null };
  sync: { running: boolean; last: SyncResult | null; supported: boolean };
  evn: { enabled: boolean; last_day: string | null; bills: number };
  forecast: { ready: boolean; model: string | null; mae_kwh: number | null; n_train: number | null; updated_at: string | null };
  assistant: boolean;
  battery_reserve_percent: number;
}

export interface SyncStartResponse {
  ok: boolean;
  reason?: "running" | "too_soon";
  retry_in?: number;
}
