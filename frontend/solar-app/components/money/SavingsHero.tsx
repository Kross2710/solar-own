import { cycleRangeLabel, solarSharePct } from "@/app/money/money.helpers";
import { fmtMoneyShort } from "@/lib/format";
import { MoneyCycle } from "@/lib/types/money";

export default function SavingsHero({ cycle }: { cycle: MoneyCycle }) {
  const sharePct = solarSharePct(cycle);

  return (
    <section className="text-center" aria-labelledby="cycle-savings">
      <span className="inline-block rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-zinc-400 tabular-nums">
        {cycleRangeLabel(cycle)} · day {cycle.days_elapsed}
      </span>

      <p className="mt-3 text-xs font-bold uppercase tracking-[0.28em] text-zinc-400" id="cycle-savings">
        Saved This Cycle
      </p>
      <p className="mt-2 bg-gradient-to-b from-white to-[#34d399] bg-clip-text text-[clamp(52px,14vw,68px)] font-extralight leading-none tracking-[-0.055em] text-transparent tabular-nums">
        {fmtMoneyShort(cycle.saved_now)}
      </p>

      {sharePct != null && (
        <div className="mx-auto mt-5 max-w-[320px]">
          <div
            className="flex h-2.5 overflow-hidden rounded-full bg-white/5"
            role="img"
            aria-label={`Solar covered ${sharePct}% of your bill`}
          >
            <span className="h-full bg-[#34d399]" style={{ width: `${sharePct}%` }} />
            <span className="h-full flex-1 bg-[#fb8a95]/70" />
          </div>

          <div className="mt-2 flex justify-between text-[11px] tabular-nums">
            <span className="text-zinc-400">
              <span className="mr-1.5 inline-block size-2 rounded-full bg-[#34d399]" />
              Saved {fmtMoneyShort(cycle.saved_now)}
            </span>
            <span className="text-zinc-400">
              <span className="mr-1.5 inline-block size-2 rounded-full bg-[#fb8a95]" />
              Paid EVN {fmtMoneyShort(cycle.bill_now)}
            </span>
          </div>

          <p className="mt-3 text-[13px] text-zinc-300">
            Solar covered <strong className="text-emerald-400">{sharePct}%</strong> of your bill
          </p>
        </div>
      )}
    </section>
  );
}
