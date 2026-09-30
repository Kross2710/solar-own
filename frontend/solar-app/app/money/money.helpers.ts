import { MONTH_NAMES, parseDateMonth } from "@/lib/format";
import { MoneyCycle, MoneyEvnHistoryItem, MoneyTier } from "@/lib/types/money";

// Flat projection scales the first few days to the whole cycle, so it is noisy early on.
const ROUGH_ESTIMATE_DAYS = 5;
const TOO_EARLY_TO_PROJECT_DAYS = 3;

// |diff| below this means the dashboard estimate matched the real EVN bill.
export const ESTIMATE_MATCH_PCT = 3;

// Leave headroom so the largest value never touches the bar's right edge.
const BILL_BAR_HEADROOM = 1.08;

// "2026-08" -> "Aug"
export function cycleMonthLabel(cycle: string): string {
  return MONTH_NAMES[parseInt(cycle.slice(5, 7)) - 1];
}

// "2026-08" -> "Aug 2026"
export function cycleMonthYearLabel(cycle: string): string {
  return `${cycleMonthLabel(cycle)} ${cycle.slice(0, 4)}`;
}

export function isTooEarlyToProject(cycle: MoneyCycle): boolean {
  return cycle.bill_proj == null || cycle.days_elapsed < TOO_EARLY_TO_PROJECT_DAYS;
}

export interface BillBarScale {
  nowPct: number;
  projPct: number;
  lastBillPct: number | null;
}

// Bar widths for "spent so far", "projected" and the last real bill marker on one shared scale.
export function billBarScale(cycle: MoneyCycle, lastBill: number | null): BillBarScale {
  const projected = cycle.bill_proj ?? cycle.bill_now;
  const max = Math.max(projected, cycle.bill_now, lastBill ?? 0) * BILL_BAR_HEADROOM;
  if (max <= 0) return { nowPct: 0, projPct: 0, lastBillPct: null };

  return {
    nowPct: (cycle.bill_now / max) * 100,
    projPct: (projected / max) * 100,
    lastBillPct: lastBill == null ? null : (lastBill / max) * 100,
  };
}

export interface YearOverYear {
  before: MoneyEvnHistoryItem;
  after: MoneyEvnHistoryItem;
  changePct: number;
}

// Latest real bill vs the same month one year earlier.
export function billYearOverYear(history: MoneyEvnHistoryItem[]): YearOverYear | null {
  const after = history[history.length - 1];
  if (!after) return null;

  const sameMonthLastYear = `${Number(after.cycle.slice(0, 4)) - 1}${after.cycle.slice(4)}`;
  const before = history.find((item) => item.cycle === sameMonthLastYear);
  if (!before || before.amount <= 0) return null;

  return {
    before,
    after,
    changePct: Math.round(((after.amount - before.amount) / before.amount) * 100),
  };
}

// Tiers from this index on are merged into one "T5+" segment to fit a phone row.
const MERGE_FROM_TIER = 4;
const OPEN_TIER_SPAN_KWH = 100;
const MIN_MERGED_SPAN_KWH = 50;
// Keep a sliver of fill visible right after entering a tier.
const MIN_TIER_FILL = 0.06;

export const TIER_WARN_KWH = 10;

export type TierSegmentState = "done" | "current" | "future";

export interface TierSegment {
  label: string;
  widthPct: number;
  state: TierSegmentState;
  fillPct: number; // progress inside the current segment, 0 otherwise
}

export interface TierRow {
  label: string;
  range: string;
  kwh: number;     // kWh of this cycle's purchase that falls inside the tier
  price: number;   // đ/kWh incl. VAT
  amount: number;
  isCurrent: boolean;
}

// How many of `kwh` fall inside each tier.
function kwhPerTier(bounds: (number | null)[], kwh: number): number[] {
  let lower = 0;
  return bounds.map((upper) => {
    const inTier = Math.max(0, Math.min(kwh, upper ?? kwh) - lower);
    if (upper != null) lower = upper;
    return inTier;
  });
}

// Per-tier breakdown of the kWh bought so far (full 6 tiers, no merging).
export function buildTierRows(tier: MoneyTier): TierRow[] {
  const perTier = kwhPerTier(tier.bounds, tier.level_kwh);

  return tier.bounds.map((upper, index) => {
    const lower = index === 0 ? 0 : (tier.bounds[index - 1] ?? 0);
    return {
      label: `T${index + 1}`,
      range: upper == null ? `>${lower}` : `${lower}–${upper}`,
      kwh: perTier[index],
      price: tier.prices[index],
      amount: Math.round(perTier[index] * tier.prices[index]),
      isCurrent: index === tier.index,
    };
  });
}

export interface BillTierRow {
  label: string;
  actual: number;       // cost of the kWh bought from EVN
  withoutSolar: number; // cost if the whole consumption were bought
}

export function buildBillTierRows(tier: MoneyTier, cycle: MoneyCycle): BillTierRow[] {
  const bought = kwhPerTier(tier.bounds, cycle.buy_kwh);
  const consumed = kwhPerTier(tier.bounds, cycle.cons_kwh);

  return tier.bounds
    .map((_, index) => ({
      label: `T${index + 1}`,
      actual: Math.round(bought[index] * tier.prices[index]),
      withoutSolar: Math.round(consumed[index] * tier.prices[index]),
    }))
    .filter((row) => row.actual > 0 || row.withoutSolar > 0);
}

export function buildTierSegments(tier: MoneyTier): TierSegment[] {
  const spans: { label: string; lower: number; span: number }[] = [];
  let lower = 0;
  let mergedLower = 0;
  let mergedSpan = 0;

  tier.bounds.forEach((upper, index) => {
    const span = upper == null ? OPEN_TIER_SPAN_KWH : upper - lower;
    if (index < MERGE_FROM_TIER) {
      spans.push({ label: `T${index + 1}`, lower, span });
    } else {
      if (index === MERGE_FROM_TIER) mergedLower = lower;
      mergedSpan += span;
    }
    if (upper != null) lower = upper;
  });
  if (tier.count > MERGE_FROM_TIER) {
    spans.push({
      label: `T${MERGE_FROM_TIER + 1}+`,
      lower: mergedLower,
      span: Math.max(mergedSpan, MIN_MERGED_SPAN_KWH),
    });
  }

  const totalSpan = spans.reduce((sum, segment) => sum + segment.span, 0);
  const currentSegment = Math.min(tier.index, spans.length - 1);

  return spans.map((segment, index) => {
    const state: TierSegmentState =
      index < currentSegment ? "done" : index === currentSegment ? "current" : "future";
    const fill =
      state === "current"
        ? Math.min(1, Math.max(MIN_TIER_FILL, (tier.level_kwh - segment.lower) / segment.span))
        : 0;

    return {
      label: segment.label,
      widthPct: (segment.span / totalSpan) * 100,
      state,
      fillPct: Math.round(fill * 100),
    };
  });
}

// Share of the would-be bill (without solar) that solar paid for, 0–100.
export function solarSharePct(cycle: MoneyCycle): number | null {
  const withoutSolar = cycle.bill_now + cycle.saved_now;
  if (withoutSolar <= 0) return null;
  return Math.round((cycle.saved_now / withoutSolar) * 100);
}

export function cycleRangeLabel(cycle: MoneyCycle): string {
  return `${parseDateMonth(cycle.start)} → ${parseDateMonth(cycle.end)}`;
}

export function isLastCycleDay(cycle: MoneyCycle): boolean {
  return cycle.days_elapsed >= cycle.days_in_cycle;
}

export function isRoughEstimate(cycle: MoneyCycle): boolean {
  return cycle.proj_method === "flat" && cycle.days_elapsed < ROUGH_ESTIMATE_DAYS;
}

export function clampPct(value: number): number {
  return Math.min(100, Math.max(0, value));
}
