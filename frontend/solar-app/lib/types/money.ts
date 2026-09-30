// Shape of GET /api/money (server.py: _compute_money + _evn_bill_block).
// All money values are rounded VND; dates are ISO "YYYY-MM-DD".

export interface MoneyTier {
  index: number;               // current tier, 0-based
  count: number;
  level_kwh: number;           // kWh bought so far this cycle
  cur_price: number;           // đ/kWh incl. VAT
  to_next_kwh: number | null;  // null when already on the top tier
  next_jump: number | null;    // extra đ/kWh on the next tier
  bounds: (number | null)[];   // upper bound per tier, null = open-ended
  prices: number[];            // đ/kWh incl. VAT per tier
}

export interface MoneyPrevCycle {
  start: string;
  days: number;                // compared over the same first N days
  has: boolean;
  buy_kwh: number;
  bill: number;
  buy_delta_pct: number | null;
  bill_delta: number;          // <= 0 means cheaper than last cycle
}

export interface MoneyToday {
  saved: number | null;
  selfuse_kwh: number | null;
}

export interface MoneyCycle {
  start: string;
  end: string;
  days_elapsed: number;
  days_in_cycle: number;
  buy_kwh: number;
  cons_kwh: number;
  bill_now: number;
  saved_now: number;
  proj_buy_kwh: number;
  proj_cons_kwh: number;
  bill_proj: number | null;
  without_solar_proj: number;
  saved_proj: number;
  bill_proj_lo: number | null;
  bill_proj_hi: number | null;
  proj_method: string;
}

export interface MoneyTotal {
  saved: number;
  months: number;
}

export interface MoneyPayback {
  invest: number;
  recovered: number;
  remaining: number;
  pct: number;
  avg_month: number;
  months_left: number | null;
  eta: string | null;
  commissioned: string | null;
  data_months: number;
  low_confidence: boolean;     // fewer than 12 months of data
  done: boolean;
}

export interface MoneyEvnBill {
  cycle: string;               // "YYYY-MM" of the last closed cycle
  amount: number;
  kwh: number | null;
  paid_date: string | null;
  est_amount: number | null;
  diff_pct: number | null;
  est_reliable: boolean;
}

export interface MoneyEvnHistoryItem {
  cycle: string;               // "YYYY-MM"
  amount: number;
}

export interface MoneyResponse {
  currency: string;
  marginal_cons: number;
  marginal_buy: number;
  tier: MoneyTier;
  prev_cycle: MoneyPrevCycle;
  today: MoneyToday;
  cycle: MoneyCycle;
  total: MoneyTotal;
  payback: MoneyPayback | null; // null when investment is not configured
  evn_bill?: MoneyEvnBill;      // absent until a closed EVN bill exists
  evn_history: MoneyEvnHistoryItem[]; // closed real bills, oldest first (up to 13)
  solar_start: string | null;   // first day with generation
}
