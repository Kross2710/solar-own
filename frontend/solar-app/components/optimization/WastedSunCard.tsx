import { fmtMoneyShort, fmtNum, parseDateMonth } from "@/lib/format";
import { CurtailmentResponse } from "@/lib/types/optimization";

type SupportedCurtailment = Extract<CurtailmentResponse, { supported: true }>;

export default function WastedSunCard({ data }: { data: SupportedCurtailment }) {
  const today = data.today;
  if (today.lost_kwh == null) return null;

  const lost30Money = data.marginal * data.total30_kwh;
  const todayMoney = data.marginal * today.lost_kwh;
  const maxLost = Math.max(...data.recent.map((item) => item.lost_kwh), 0.1);

  return (
    <section
      className="rounded-[22px] border border-white/10 border-t-amber-300/20 bg-[#0a0e18]/90 p-3 shadow-2xl backdrop-blur-xl sm:p-4"
      aria-labelledby="wasted-sun"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-zinc-100" id="wasted-sun">
          <i className="fa-solid fa-sun mr-1.5 text-[#ffc76b]" />
          Wasted sun
        </h2>
        <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] font-semibold text-zinc-400">estimate</span>
      </div>

      <div className="mt-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-[11px] text-zinc-400">{data.days === 1 ? "Today so far" : `Last ${data.days} days`}</p>
          <p className="mt-1 text-2xl font-bold leading-none tabular-nums text-zinc-100">~{fmtMoneyShort(lost30Money)}</p>
          <p className="mt-1 text-[11px] text-zinc-500">{fmtNum(data.total30_kwh)} kWh the battery had no room for</p>
        </div>
        <div className="text-right">
          <p className="text-[11px] text-zinc-400">Today</p>
          <p className="mt-1 text-base font-bold tabular-nums text-[#ffc76b]">{fmtNum(today.lost_kwh, 1)} kWh</p>
          <p className="text-[11px] tabular-nums text-zinc-500">~{fmtMoneyShort(todayMoney)}</p>
        </div>
      </div>

      {data.recent.length > 1 && (
        <div className="mt-3 flex h-10 items-end gap-[2px]" role="img" aria-label={`Wasted sun per day, last ${data.recent.length} days`}>
          {data.recent.map((item, index) => (
            <span
              key={item.day}
              className={`flex-1 rounded-t-[2px] ${index === data.recent.length - 1 ? "bg-[#ffc76b]" : "bg-[#ffc76b]/35"}`}
              style={{ height: `${Math.max(6, (item.lost_kwh / maxLost) * 100)}%` }}
              title={`${parseDateMonth(item.day)}: ${fmtNum(item.lost_kwh, 1)} kWh`}
            />
          ))}
        </div>
      )}

      <p className="mt-3 text-[12px] leading-relaxed text-zinc-300">
        {today.full_at ? (
          <>
            Battery was full at <strong className="text-zinc-100">{today.full_at}</strong> — run heavy loads after that
            to use the surplus instead of losing it.
          </>
        ) : today.lost_kwh > 0 ? (
          "Midday surplus sun was curtailed — shift heavy loads into midday."
        ) : (
          "Almost nothing wasted today."
        )}
      </p>
    </section>
  );
}
