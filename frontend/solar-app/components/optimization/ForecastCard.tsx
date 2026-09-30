import {
  dayOfWeek,
  isFlatForecast,
  RAIN_SHOWN_FROM_PCT,
  weatherIcon,
} from "@/app/optimization/optimization.helpers";
import { ForecastDay } from "@/lib/types/optimization";

const DAYS_SHOWN = 5;
const BAR_MAX_PX = 44;

interface ForecastCardProps {
  days: ForecastDay[];
  avg30: number | null;
  mae: number | null;
}

export default function ForecastCard({ days, avg30, mae }: ForecastCardProps) {
  const shown = days.slice(0, DAYS_SHOWN);
  if (!shown.length) return null;

  const flat = isFlatForecast(shown);
  const scale = Math.max(...shown.map((day) => day.kwh ?? 0), avg30 ?? 0, 1);
  const avgPx = avg30 != null ? (avg30 / scale) * BAR_MAX_PX : null;
  const roundedMae = mae != null ? Math.round(mae) : null;
  const note = flat
    ? `Similar weather ahead · output about the same${roundedMae != null ? ` (±${roundedMae} kWh)` : ""}`
    : roundedMae != null
      ? `may vary ±${roundedMae} kWh with the weather`
      : "weather-based forecast";

  return (
    <section
      className="rounded-[22px] border border-white/10 border-t-amber-300/20 bg-[#0a0e18]/90 p-3 shadow-2xl backdrop-blur-xl sm:p-4"
      aria-labelledby="next-days"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-bold text-zinc-100" id="next-days">Next {shown.length} days</h2>
        <span className="text-right text-[11px] text-zinc-500">{note}</span>
      </div>

      <div className="relative mt-4 grid grid-cols-5 gap-1.5">
        {shown.map((day) => {
          const icon = weatherIcon(day.wcode);
          const barPx = day.kwh != null ? Math.max(4, (day.kwh / scale) * BAR_MAX_PX) : 0;
          return (
            <div
              key={day.date}
              className={`flex flex-col items-center rounded-xl px-1 py-2 text-center ${
                day.today ? "bg-white/[0.06] ring-1 ring-inset ring-white/10" : ""
              }`}
            >
              <p className={`text-[11px] font-semibold ${day.today ? "text-zinc-100" : "text-zinc-400"}`}>
                {day.today ? "Today" : dayOfWeek(day.date)}
              </p>
              <i className={`fa-solid ${icon.icon} ${icon.className} mt-1.5 text-base`} aria-hidden="true" />

              <div className="relative mt-2 flex w-full justify-center" style={{ height: BAR_MAX_PX }}>
                {avgPx != null && (
                  <span
                    className="absolute inset-x-0 border-t border-dashed border-white/20"
                    style={{ bottom: avgPx }}
                    aria-hidden="true"
                  />
                )}
                <span
                  className="mt-auto w-3 rounded-t-[3px] bg-gradient-to-t from-[#ffc76b]/40 to-[#ffc76b]"
                  style={{ height: barPx }}
                  aria-hidden="true"
                />
              </div>

              <p className="mt-1.5 text-[13px] font-bold tabular-nums text-zinc-100">
                {day.kwh == null ? "–" : `${flat ? "~" : ""}${Math.round(day.kwh)}`}
                <span className="ml-0.5 text-[9px] font-medium text-zinc-500">kWh</span>
              </p>
              <p className="text-[10px] tabular-nums text-zinc-500">
                {day.tmax != null ? `${Math.round(day.tmax)}°` : "–"}/{day.tmin != null ? `${Math.round(day.tmin)}°` : "–"}
              </p>
              <p className="h-4 text-[10px] tabular-nums text-[#7dd3fc]">
                {day.rain_prob != null && day.rain_prob >= RAIN_SHOWN_FROM_PCT && (
                  <>
                    <i className="fa-solid fa-umbrella mr-0.5" />
                    {Math.round(day.rain_prob)}%
                  </>
                )}
              </p>
            </div>
          );
        })}
      </div>

      {avg30 != null && (
        <p className="mt-2 text-[10px] text-zinc-500">
          <span className="mr-1.5 inline-block w-4 border-t border-dashed border-white/30 align-middle" />
          30-day average {Math.round(avg30)} kWh
        </p>
      )}
    </section>
  );
}
