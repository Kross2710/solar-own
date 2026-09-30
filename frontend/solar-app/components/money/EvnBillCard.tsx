import type { CSSProperties } from "react";
import {
  billBarScale,
  billYearOverYear,
  buildBillTierRows,
  cycleMonthLabel,
  cycleMonthYearLabel,
  ESTIMATE_MATCH_PCT,
  isTooEarlyToProject,
} from "@/app/money/money.helpers";
import BillHistoryChart from "@/components/money/BillHistoryChart";
import DetailsDisclosure from "@/components/money/DetailsDisclosure";
import { fmtMoney, fmtMoneyK, fmtMoneyShort, fmtNum, parseDateMonth } from "@/lib/format";
import {
  MoneyCycle,
  MoneyEvnBill,
  MoneyEvnHistoryItem,
  MoneyPrevCycle,
  MoneyTier,
} from "@/lib/types/money";

interface EvnBillCardProps {
  cycle: MoneyCycle;
  prevCycle: MoneyPrevCycle;
  tier: MoneyTier;
  evnBill?: MoneyEvnBill;
  history: MoneyEvnHistoryItem[];
  solarStart: string | null;
}

// Keep the marker label inside the card near both edges.
function markerLabelStyle(pct: number): CSSProperties {
  const shift = pct > 75 ? "-100%" : pct < 25 ? "0" : "-50%";
  return { left: `${pct}%`, transform: `translateX(${shift})` };
}

function ThisCycle({ cycle, prevCycle, lastBill }: {
  cycle: MoneyCycle;
  prevCycle: MoneyPrevCycle;
  lastBill?: MoneyEvnBill;
}) {
  const tooEarly = isTooEarlyToProject(cycle);
  const scale = billBarScale(cycle, lastBill?.amount ?? null);
  const cheaper = prevCycle.bill_delta <= 0;

  return (
    <div>
      <p className="text-[11px] text-zinc-400">{tooEarly ? "Owed so far" : "Projected this cycle"}</p>
      <p className="mt-1 text-2xl font-bold leading-none tabular-nums text-zinc-100">
        {tooEarly ? fmtMoneyK(cycle.bill_now) : `~${fmtMoneyK(cycle.bill_proj)}`}
      </p>
      <p className="mt-1.5 text-[11px] leading-snug text-zinc-400">
        {tooEarly
          ? `Too early to project · ${fmtNum(cycle.buy_kwh)} kWh bought`
          : `so far ${fmtMoneyShort(cycle.bill_now)} · ${fmtNum(cycle.buy_kwh)} of ~${fmtNum(cycle.proj_buy_kwh)} kWh bought`}
      </p>

      <div className={`relative mt-3 ${scale.lastBillPct != null ? "mb-5" : ""}`}>
        <div className="relative h-2 overflow-hidden rounded-full bg-white/5">
          {!tooEarly && (
            <span className="absolute inset-y-0 left-0 rounded-full bg-[#fb8a95]/25" style={{ width: `${scale.projPct}%` }} />
          )}
          <span className="absolute inset-y-0 left-0 rounded-full bg-[#fb8a95]" style={{ width: `${scale.nowPct}%` }} />
        </div>
        {scale.lastBillPct != null && lastBill && (
          <>
            <span
              className="absolute -top-1 h-4 w-0.5 -translate-x-1/2 rounded-full bg-zinc-200"
              style={{ left: `${scale.lastBillPct}%` }}
              aria-hidden="true"
            />
            <span
              className="absolute top-4 whitespace-nowrap text-[10px] tabular-nums text-zinc-400"
              style={markerLabelStyle(scale.lastBillPct)}
            >
              {cycleMonthLabel(lastBill.cycle)} bill {fmtMoneyShort(lastBill.amount)}
            </span>
          </>
        )}
      </div>

      {prevCycle.has && (
        <p className="mt-2 text-[11px] text-zinc-400">
          <span
            className={`mr-1.5 rounded-full px-2 py-0.5 font-bold tabular-nums ${
              cheaper ? "bg-emerald-400/10 text-emerald-400" : "bg-[#fb8a95]/10 text-[#fb8a95]"
            }`}
          >
            {cheaper ? "▼" : "▲"} {fmtMoneyShort(Math.abs(prevCycle.bill_delta))}
          </span>
          vs {cycleMonthLabel(prevCycle.start)} over the same {prevCycle.days} days
        </p>
      )}
    </div>
  );
}

function LastBill({ bill }: { bill: MoneyEvnBill }) {
  const details = [
    bill.kwh != null ? `${fmtNum(bill.kwh)} kWh` : null,
    bill.paid_date ? `paid ${parseDateMonth(bill.paid_date)}` : null,
  ].filter(Boolean);
  const showCheck = bill.est_reliable && bill.diff_pct != null;
  const matched = showCheck && Math.abs(bill.diff_pct!) < ESTIMATE_MATCH_PCT;

  return (
    <div className="mt-4 border-t border-white/10 pt-3">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <p className="text-[12px] font-semibold text-zinc-200">{cycleMonthLabel(bill.cycle)} bill</p>
          {details.length > 0 && <p className="mt-0.5 text-[11px] text-zinc-500">{details.join(" · ")}</p>}
        </div>
        <p className="text-base font-bold tabular-nums text-zinc-100">{fmtMoney(bill.amount)}</p>
      </div>

      {showCheck && (
        <p className={`mt-2 text-[11px] ${matched ? "text-emerald-400" : "text-[#ffcaa6]"}`}>
          <i className={`fa-solid ${matched ? "fa-circle-check" : "fa-circle-exclamation"} mr-1.5`} />
          {matched
            ? `Our estimate was within ${Math.abs(bill.diff_pct!)}% of this bill`
            : `Our estimate was off by ${Math.abs(bill.diff_pct!)}% for this bill`}
        </p>
      )}
    </div>
  );
}

function BillBreakdown({ tier, cycle }: { tier: MoneyTier; cycle: MoneyCycle }) {
  const rows = buildBillTierRows(tier, cycle);
  const withoutSolar = cycle.bill_now + cycle.saved_now;

  return (
    <div>
      <div className="grid grid-cols-[1fr_auto_auto] gap-x-3 gap-y-1.5 text-[12px] tabular-nums">
        <span className="text-zinc-500">Tier</span>
        <span className="text-right text-zinc-500">Actual</span>
        <span className="text-right text-zinc-500">Without solar</span>
        {rows.map((row) => (
          <div className="contents" key={row.label}>
            <span className="text-zinc-300">{row.label}</span>
            <span className="text-right text-zinc-300">{fmtNum(row.actual)}</span>
            <span className="text-right text-zinc-500">{fmtNum(row.withoutSolar)}</span>
          </div>
        ))}
      </div>

      <div className="mt-3 space-y-1 border-t border-white/10 pt-2 text-[13px] tabular-nums">
        <div className="flex justify-between">
          <span className="text-zinc-300">Owed so far</span>
          <strong className="text-zinc-100">{fmtMoney(cycle.bill_now)}</strong>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-400">Without solar</span>
          <strong className="text-zinc-400">{fmtMoney(withoutSolar)}</strong>
        </div>
        <div className="flex justify-between text-emerald-400">
          <span>Solar saved</span>
          <strong>{fmtMoney(cycle.saved_now)}</strong>
        </div>
      </div>
    </div>
  );
}

function BillHistory({ history, solarStart }: { history: MoneyEvnHistoryItem[]; solarStart: string | null }) {
  const yoy = billYearOverYear(history);

  return (
    <div className="mt-4 border-t border-white/10 pt-3">
      <p className="text-[12px] font-semibold text-zinc-200">Real EVN bills · last {history.length} cycles</p>
      {yoy && (
        <p className="mt-1 text-[11px] tabular-nums text-zinc-400">
          {cycleMonthYearLabel(yoy.before.cycle)} {fmtMoneyShort(yoy.before.amount)} →{" "}
          {cycleMonthYearLabel(yoy.after.cycle)} {fmtMoneyShort(yoy.after.amount)}{" "}
          <strong className={yoy.changePct <= 0 ? "text-emerald-400" : "text-[#fb8a95]"}>
            {yoy.changePct > 0 ? "+" : ""}
            {yoy.changePct}%
          </strong>
        </p>
      )}
      <div className="mt-2">
        <BillHistoryChart history={history} solarStart={solarStart} />
      </div>
    </div>
  );
}

export default function EvnBillCard({ cycle, prevCycle, tier, evnBill, history, solarStart }: EvnBillCardProps) {
  return (
    <section
      className="rounded-[22px] border border-white/10 border-t-[#fb8a95]/25 bg-[#0a0e18]/90 p-3 shadow-2xl backdrop-blur-xl sm:p-4"
      aria-labelledby="evn-bill"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-zinc-100" id="evn-bill">
          <i className="fa-solid fa-file-invoice mr-1.5 text-[#fb8a95]" />
          EVN bill
        </h2>
        <span className="text-[11px] text-zinc-500">{cycleMonthLabel(cycle.start)} cycle</span>
      </div>

      <div className="mt-3">
        <ThisCycle cycle={cycle} prevCycle={prevCycle} lastBill={evnBill} />
      </div>

      {evnBill && <LastBill bill={evnBill} />}

      <DetailsDisclosure>
        <div className="border-t border-white/10 pt-3">
          <BillBreakdown tier={tier} cycle={cycle} />
          {history.length > 0 && <BillHistory history={history} solarStart={solarStart} />}
        </div>
      </DetailsDisclosure>
    </section>
  );
}
