import { clampPct, isLastCycleDay, isRoughEstimate } from "@/app/money/money.helpers";
import { fmtMoneyShort } from "@/lib/format";
import { MoneyCycle, MoneyPayback, MoneyToday, MoneyTotal } from "@/lib/types/money";

interface SavingsCardsProps {
  today: MoneyToday;
  cycle: MoneyCycle;
  total: MoneyTotal;
  payback: MoneyPayback | null;
}

const cardClass = "rounded-xl border border-white/10 bg-black/10 p-3";

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="mt-2.5 h-1 overflow-hidden rounded-full bg-white/10">
      <span className="block h-full rounded-full bg-[#34d399]" style={{ width: `${clampPct(pct)}%` }} />
    </div>
  );
}

function TodayCard({ today }: { today: MoneyToday }) {
  const hasData = today.saved != null;

  return (
    <article className={cardClass}>
      <p className="text-[11px] text-zinc-400">Today</p>
      <p className="mt-1 text-lg font-bold leading-none tabular-nums text-emerald-400">
        {hasData ? `+${fmtMoneyShort(today.saved)}` : "—"}
      </p>
      <p className="mt-1 text-[11px] leading-snug text-zinc-400">
        {hasData ? `${today.selfuse_kwh} kWh used from solar` : "Waiting for data"}
      </p>
    </article>
  );
}

function FullCycleCard({ cycle }: { cycle: MoneyCycle }) {
  const lastDay = isLastCycleDay(cycle);
  const progressPct = (cycle.days_elapsed / cycle.days_in_cycle) * 100;

  return (
    <article className={cardClass}>
      <p className="text-[11px] text-zinc-400">Full cycle</p>
      <p className="mt-1 text-lg font-bold leading-none tabular-nums text-zinc-100">
        {lastDay ? fmtMoneyShort(cycle.saved_now) : `~${fmtMoneyShort(cycle.saved_proj)}`}
      </p>
      <p className="mt-1 text-[11px] leading-snug text-zinc-400">
        {lastDay
          ? "Cycle closes today"
          : isRoughEstimate(cycle)
            ? "Rough estimate, early in cycle"
            : `Day ${cycle.days_elapsed} of ${cycle.days_in_cycle}`}
      </p>
      <ProgressBar pct={progressPct} />
    </article>
  );
}

function AllTimeCard({ total, payback }: { total: MoneyTotal; payback: MoneyPayback | null }) {
  return (
    <article className={`${cardClass} col-span-2`}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[11px] text-zinc-400">All-time</p>
        {total.months > 0 && (
          <p className="text-[11px] text-zinc-500">over {total.months} months</p>
        )}
      </div>
      <p className="mt-1 text-lg font-bold leading-none tabular-nums text-zinc-100">
        {fmtMoneyShort(total.saved)}
      </p>

      {payback && (
        <>
          <ProgressBar pct={payback.pct} />
          <p className="mt-1.5 text-[11px] leading-snug text-zinc-400">
            {payback.done
              ? "Investment fully paid back"
              : `${payback.pct}% of ${fmtMoneyShort(payback.invest)} paid back`}
          </p>
        </>
      )}
    </article>
  );
}

export default function SavingsCards({ today, cycle, total, payback }: SavingsCardsProps) {
  return (
    <section className="grid grid-cols-2 gap-2" aria-label="Savings">
      <TodayCard today={today} />
      <FullCycleCard cycle={cycle} />
      <AllTimeCard total={total} payback={payback} />
    </section>
  );
}
