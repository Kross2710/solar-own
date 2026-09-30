"use client";

import { useState } from "react";
import {
  bestWindow,
  fmtDuration,
  HourCell,
  HourLevel,
  minutesLeftInWindow,
} from "@/app/optimization/optimization.helpers";

const levelClass: Record<HourLevel, string> = {
  cheap: "bg-[#ffc76b] shadow-[0_0_8px_rgba(255,199,107,0.4)]",
  mid: "bg-[#b8a6ff]/55",
  dear: "bg-[#fb8a95]/40",
  none: "bg-white/[0.08]",
};

const AXIS_HOURS = [0, 6, 12, 18, 24];

function hourLabel(hour: number): string {
  return `${String(hour).padStart(2, "0")}h`;
}

export default function BestHoursCard({ cells, now }: { cells: HourCell[]; now: Date }) {
  const currentHour = now.getHours();
  const [selectedHour, setSelectedHour] = useState(currentHour);

  if (!cells.length || cells.every((cell) => cell.level === "none")) return null;

  const best = bestWindow(cells);
  const minutesLeft = best ? minutesLeftInWindow(best, now) : null;
  const selected = cells.find((cell) => cell.hour === selectedHour) ?? cells[0];

  return (
    <section
      className="rounded-[22px] border border-white/10 border-t-amber-300/20 bg-[#0a0e18]/90 p-3 shadow-2xl backdrop-blur-xl sm:p-4"
      aria-labelledby="best-hours"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-bold text-zinc-100" id="best-hours">
          <i className="fa-solid fa-clock mr-1.5 text-[#ffc76b]" />
          Best hours today
        </h2>
        <span className="text-[11px] text-zinc-500">based on the last 30 days</span>
      </div>

      {best && (
        <p className="mt-2 text-[13px] text-zinc-300">
          <strong className="text-[#ffc76b]">
            {best.from}h–{best.to}h
          </strong>{" "}
          for heavy loads
          {minutesLeft != null && <span className="text-emerald-400"> · {fmtDuration(minutesLeft)} left</span>}
        </p>
      )}

      <div className="mt-3 flex h-9 gap-[2px]" role="group" aria-label="Hours of the day">
        {cells.map((cell) => (
          <button
            key={cell.hour}
            type="button"
            className={`relative flex-1 rounded-[3px] transition-transform ${levelClass[cell.level]} ${
              cell.hour === selectedHour ? "scale-y-110 ring-2 ring-white/90" : ""
            }`}
            aria-label={`${hourLabel(cell.hour)}: ${cell.description}`}
            aria-pressed={cell.hour === selectedHour}
            onClick={() => setSelectedHour(cell.hour)}
          >
            {cell.hour === currentHour && (
              <span className="absolute -top-2 left-1/2 size-1.5 -translate-x-1/2 rounded-full bg-white" aria-hidden="true" />
            )}
          </button>
        ))}
      </div>

      <div className="mt-1.5 flex justify-between text-[10px] tabular-nums text-zinc-500">
        {AXIS_HOURS.map((hour) => (
          <span key={hour}>{hour}h</span>
        ))}
      </div>

      <div className="mt-3 flex items-center justify-between gap-3 rounded-xl bg-white/[0.04] px-3 py-2 text-[12px]" aria-live="polite">
        <span className="text-zinc-200">
          <strong className="tabular-nums">{hourLabel(selected.hour)}</strong>
          {selected.hour === currentHour && <span className="text-zinc-500"> · now</span>}
          <span className="text-zinc-400"> · {selected.description}</span>
        </span>
        {selected.cost && (
          <span className={`shrink-0 font-semibold tabular-nums ${{ cheap: "text-emerald-400", mid: "text-[#b8a6ff]", dear: "text-[#fb8a95]", none: "" }[selected.level]}`}>
            {selected.cost}
          </span>
        )}
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-zinc-400">
        <span><i className={`mr-1.5 inline-block size-2.5 rounded-[3px] align-middle ${levelClass.cheap}`} />Free (spare sun)</span>
        <span><i className={`mr-1.5 inline-block size-2.5 rounded-[3px] align-middle ${levelClass.mid}`} />Battery</span>
        <span><i className={`mr-1.5 inline-block size-2.5 rounded-[3px] align-middle ${levelClass.dear}`} />Grid</span>
      </div>
    </section>
  );
}
