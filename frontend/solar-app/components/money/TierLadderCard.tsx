import type { CSSProperties } from "react";
import { buildTierRows, buildTierSegments, TIER_WARN_KWH, TierSegment } from "@/app/money/money.helpers";
import DetailsDisclosure from "@/components/money/DetailsDisclosure";
import { fmtMoney, fmtNum } from "@/lib/format";
import { MoneyTier } from "@/lib/types/money";

function segmentStyle(segment: TierSegment) {
  const style: CSSProperties = { flex: `${segment.widthPct} 1 0`, minWidth: 0 };
  if (segment.state === "current") {
    style.background = `linear-gradient(90deg, rgba(255,199,107,0.9) 0 ${segment.fillPct}%, rgba(255,199,107,0.22) ${segment.fillPct}%)`;
  }
  return style;
}

const segmentClass: Record<TierSegment["state"], string> = {
  done: "bg-[#7dd3fc]/75 text-[#04060c] font-bold",
  current: "text-[#04060c] font-bold shadow-[0_0_12px_rgba(255,199,107,0.3)]",
  future: "bg-white/5 text-zinc-500 font-semibold",
};

function TierMessage({ tier }: { tier: MoneyTier }) {
  const bought = Math.round(tier.level_kwh);

  if (tier.to_next_kwh == null) {
    return (
      <p className="mt-3 text-[12px] leading-relaxed text-zinc-300">
        On <strong className="text-zinc-100">tier {tier.count}</strong> (highest) · bought {bought} kWh this cycle
      </p>
    );
  }

  const near = tier.to_next_kwh < TIER_WARN_KWH;
  const nextPrice = tier.prices[tier.index + 1];

  return (
    <p className={`mt-3 text-[12px] leading-relaxed ${near ? "font-semibold text-[#ffcaa6]" : "text-zinc-300"}`}>
      {near && <i className="fa-solid fa-triangle-exclamation mr-1.5 text-[#ffc76b]" />}
      Bought <strong className="text-zinc-100">{bought} kWh</strong> —{" "}
      <strong className="text-[#ffc76b]">{Math.round(tier.to_next_kwh)} kWh</strong> to go until tier {tier.index + 2}
      {nextPrice != null && (
        <span className="text-zinc-400"> ({fmtMoney(nextPrice)}/kWh, +{fmtMoney(tier.next_jump)})</span>
      )}
    </p>
  );
}

function TierBreakdown({ tier, billNow }: { tier: MoneyTier; billNow: number }) {
  const rows = buildTierRows(tier);

  return (
    <div className="border-t border-white/10 pt-3">
      <div className="grid grid-cols-[1fr_auto_auto] gap-x-3 gap-y-1.5 text-[12px] tabular-nums">
        <span className="text-zinc-500">Tier</span>
        <span className="text-right text-zinc-500">kWh × đ</span>
        <span className="text-right text-zinc-500">Amount</span>

        {rows.map((row) => {
          const tone = row.isCurrent
            ? "font-bold text-[#ffc76b]"
            : row.kwh <= 0
              ? "text-zinc-300 opacity-40"
              : "text-zinc-300";
          return (
            <div className="contents" key={row.label}>
              <span className={tone}>
                {row.label} <span className="opacity-70">{row.range}</span>
                {row.isCurrent && " ◄"}
              </span>
              <span className={`text-right ${tone}`}>
                {fmtNum(row.kwh)} × {fmtNum(row.price)}
              </span>
              <span className={`text-right ${tone}`}>{fmtNum(row.amount)}</span>
            </div>
          );
        })}
      </div>

      <div className="mt-3 flex justify-between border-t border-white/10 pt-2 text-[13px]">
        <span className="text-zinc-300">So far</span>
        <strong className="font-bold tabular-nums text-zinc-100">{fmtMoney(billNow)}</strong>
      </div>
    </div>
  );
}

export default function TierLadderCard({ tier, billNow }: { tier: MoneyTier; billNow: number }) {
  if (!tier.count) return null;

  const segments = buildTierSegments(tier);

  return (
    <section
      className="rounded-[22px] border border-white/10 border-t-amber-300/20 bg-[#0a0e18]/90 p-3 shadow-2xl backdrop-blur-xl sm:p-4"
      aria-labelledby="price-tiers"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-zinc-100" id="price-tiers">
          <i className="fa-solid fa-stairs mr-1 text-[#ffc76b]" />
          Price tiers
        </h2>
        <span className="text-xs font-bold tabular-nums text-[#ffc76b]">{fmtMoney(tier.cur_price)}/kWh</span>
      </div>

      <div className="mt-3 flex gap-1" role="img" aria-label={`Tier ${tier.index + 1} of ${tier.count}`}>
        {segments.map((segment) => (
          <div
            key={segment.label}
            className={`flex h-[26px] items-center justify-center overflow-hidden whitespace-nowrap rounded-[5px] text-[10px] ${segmentClass[segment.state]}`}
            style={segmentStyle(segment)}
          >
            {segment.label}
            {segment.state === "current" && " · now"}
          </div>
        ))}
      </div>

      <TierMessage tier={tier} />

      <DetailsDisclosure>
        <TierBreakdown tier={tier} billNow={billNow} />
      </DetailsDisclosure>
    </section>
  );
}
