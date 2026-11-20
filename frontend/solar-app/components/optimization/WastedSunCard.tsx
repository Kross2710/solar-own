import { fmtMoneyShort, fmtNum, parseDateMonth } from "@/lib/format";
import { CurtailmentResponse } from "@/lib/types/optimization";
import Card from "@/components/Card";

type SupportedCurtailment = Extract<CurtailmentResponse, { supported: true }>;

export default function WastedSunCard({ data }: { data: SupportedCurtailment }) {
  const today = data.today;
  const satellite = data.method === "satellite";

  const todayMoney = data.today_grid_reduction_value;
  const maxLost = Math.max(...data.recent.map((item) => item.lost_kwh), 0.1);

  return (
    <Card
      accent="pv"
      aria-labelledby="wasted-sun"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-zinc-100" id="wasted-sun">
          <i className="fa-solid fa-sun mr-1.5 text-pv" />
          Wasted sun
        </h2>
        <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] font-semibold text-zinc-400">{satellite ? "Satellite estimate" : "Estimate"}</span>
      </div>

      <div className="mt-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-[11px] text-zinc-400">{satellite ? `${data.days} of the past 30 days` : data.days === 1 ? "Today so far" : `Last ${data.days} days`}</p>
          <p className="mt-1 text-2xl font-bold leading-none tabular-nums text-zinc-100">{data.total30_kwh == null ? "Unavailable" : `${fmtNum(data.total30_kwh, 1)} kWh`}</p>
          <p className="mt-1 text-[11px] text-zinc-500">estimated solar curtailed while the battery was full</p>
        </div>
        <div className="text-right">
          <p className="text-[11px] text-zinc-400">Today</p>
          <p className="mt-1 text-base font-bold tabular-nums text-pv">{today.lost_kwh == null ? "Unavailable" : `${fmtNum(today.lost_kwh, 1)} kWh`}</p>
          <p className="text-[11px] tabular-nums text-zinc-500">{satellite && today.lost_kwh == null ? "Waiting for satellite and inverter data" :
            satellite && (today.covered_minutes ?? 0) < 720 ? `${today.covered_minutes} min of daylight covered` :
            todayMoney == null ? "Value unavailable" : `~${fmtMoneyShort(todayMoney)} tariff equivalent`}</p>
        </div>
      </div>

      {data.recent.length > 1 && (
        <div className="mt-3 flex h-10 items-end gap-[2px]" role="img" aria-label={`Wasted sun per day, last ${data.recent.length} days`}>
          {data.recent.map((item, index) => (
            <span
              key={item.day}
              className={`flex-1 rounded-t-[2px] ${index === data.recent.length - 1 ? "bg-pv" : "bg-pv/35"}`}
              style={{ height: `${Math.max(6, (item.lost_kwh / maxLost) * 100)}%` }}
              title={`${parseDateMonth(item.day)}: ${fmtNum(item.lost_kwh, 1)} kWh`}
            />
          ))}
        </div>
      )}

      <p className="mt-3 text-[11px] text-zinc-500">Tariff equivalent assumes this energy replaces grid purchases in the projected cycle. Actual savings require shifting existing loads; surplus alone is not lost money.</p>
      <p className="mt-3 text-[12px] leading-relaxed text-zinc-300">
        {today.lost_kwh == null ? null : today.full_at ? (
          <>
            Battery reached full at <strong className="text-zinc-100">{today.full_at}</strong> today. On similar days, move existing flexible loads into the midday surplus.
          </>
        ) : today.lost_kwh > 0 ? (
          "Midday surplus sun was curtailed — shift heavy loads into midday."
        ) : (
          "Almost nothing wasted today."
        )}
      </p>
    </Card>
  );
}
