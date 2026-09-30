import type { CSSProperties } from "react";
import { BatteryPlan, DayKind } from "@/app/optimization/optimization.helpers";
import { fmtNum } from "@/lib/format";

interface TonightHeroProps {
  kind: DayKind | null;
  tomorrowKwh: number | null;
  advice: string;
  plan: BatteryPlan | null;
}

const KIND_LABEL: Record<DayKind, string> = { sunny: "Sunny", mid: "Fair sun", poor: "Little sun" };
const KIND_ICON: Record<DayKind, string> = { sunny: "fa-sun", mid: "fa-cloud-sun", poor: "fa-cloud-rain" };
// Leave headroom so the larger of usable/need never touches the bar end.
const BAR_HEADROOM = 1.1;

function markerLabelStyle(pct: number): CSSProperties {
  const shift = pct > 75 ? "-100%" : pct < 25 ? "0" : "-50%";
  return { left: `${pct}%`, transform: `translateX(${shift})` };
}

function BatteryTonight({ plan }: { plan: BatteryPlan }) {
  const scale = Math.max(plan.usableKwh, plan.needKwh ?? 0, 0.1) * BAR_HEADROOM;
  const usablePct = (plan.usableKwh / scale) * 100;
  const needPct = plan.needKwh != null ? (plan.needKwh / scale) * 100 : null;

  return (
    <div className="mx-auto mt-5 max-w-[340px] text-left">
      <div className="flex items-baseline justify-between text-[11px] text-zinc-400">
        <span>
          <i className="fa-solid fa-battery-three-quarters mr-1.5 text-[#b8a6ff]" />
          Battery tonight · {Math.round(plan.socPct)}%
        </span>
        <span className="tabular-nums text-zinc-200">{fmtNum(plan.usableKwh, 1)} kWh usable</span>
      </div>

      <div className={`relative mt-2 ${needPct != null ? "mb-5" : ""}`}>
        <div className="h-2.5 overflow-hidden rounded-full bg-white/5">
          <span
            className={`block h-full rounded-full ${plan.enough === false ? "bg-[#b8a6ff]/60" : "bg-[#b8a6ff]"}`}
            style={{ width: `${usablePct}%` }}
          />
        </div>
        {needPct != null && (
          <>
            <span
              className="absolute -top-1 h-[18px] w-0.5 -translate-x-1/2 rounded-full bg-zinc-200"
              style={{ left: `${needPct}%` }}
              aria-hidden="true"
            />
            <span
              className="absolute top-[18px] whitespace-nowrap text-[10px] tabular-nums text-zinc-400"
              style={markerLabelStyle(needPct)}
            >
              night needs ~{fmtNum(plan.needKwh, 1)} kWh
            </span>
          </>
        )}
      </div>
    </div>
  );
}

export default function TonightHero({ kind, tomorrowKwh, advice, plan }: TonightHeroProps) {
  const enough = plan?.enough;

  return (
    <section className="text-center" aria-labelledby="tomorrow-forecast">
      <p className="text-xs font-bold uppercase tracking-[0.28em] text-zinc-400" id="tomorrow-forecast">
        Tomorrow
      </p>
      <p className="mt-2 bg-gradient-to-b from-white to-[#ffc76b] bg-clip-text text-[clamp(52px,14vw,68px)] font-extralight leading-none tracking-[-0.055em] text-transparent tabular-nums">
        {tomorrowKwh != null ? (
          <>
            ~{Math.round(tomorrowKwh)}
            <span className="ml-1 text-[0.4em] tracking-normal">kWh</span>
          </>
        ) : (
          "—"
        )}
      </p>
      {kind && (
        <span className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-[#ffc76b]/25 bg-[#ffc76b]/10 px-3 py-1 text-[11px] font-semibold text-[#ffc76b]">
          <i className={`fa-solid ${KIND_ICON[kind]}`} />
          {KIND_LABEL[kind]} expected
        </span>
      )}

      {plan && <BatteryTonight plan={plan} />}

      <p
        className={`mx-auto mt-3 max-w-[340px] text-[13px] leading-relaxed ${
          enough === false ? "text-[#ffcaa6]" : "text-zinc-300"
        }`}
      >
        {advice}
      </p>
    </section>
  );
}
