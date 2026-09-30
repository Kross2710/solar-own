import { Suggestion, SuggestionTone } from "@/app/optimization/optimization.helpers";

const iconTone: Record<SuggestionTone, string> = {
  load: "bg-[#7dd3fc]/10 text-[#7dd3fc] ring-[#7dd3fc]/35",
  batt: "bg-[#b8a6ff]/10 text-[#b8a6ff] ring-[#b8a6ff]/35",
  warn: "bg-[#fb8a95]/10 text-[#fb8a95] ring-[#fb8a95]/35",
};

const valueTone: Record<Suggestion["valueTone"], string> = {
  good: "text-emerald-400",
  bad: "text-[#fb8a95]",
  neutral: "text-zinc-200",
};

export default function DoNowCard({ suggestions }: { suggestions: Suggestion[] }) {
  if (!suggestions.length) return null;

  return (
    <section
      className="rounded-[22px] border border-white/10 border-t-sky-300/20 bg-[#0a0e18]/90 p-3 shadow-2xl backdrop-blur-xl sm:p-4"
      aria-labelledby="do-now"
    >
      <h2 className="text-sm font-bold text-zinc-100" id="do-now">
        <i className="fa-solid fa-bolt mr-1.5 text-[#7dd3fc]" />
        What to do today
      </h2>

      <ul className="mt-3 divide-y divide-white/5">
        {suggestions.map((item) => (
          <li className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0" key={item.id}>
            <span className={`grid size-9 shrink-0 place-items-center rounded-xl ring-1 ring-inset ${iconTone[item.tone]}`}>
              <i className={`fa-solid ${item.icon}`} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold leading-snug text-zinc-100">{item.title}</p>
              <p className="mt-0.5 text-[11px] leading-snug text-zinc-400">{item.detail}</p>
            </div>
            <div className="shrink-0 text-right">
              <p className={`text-[13px] font-bold tabular-nums ${valueTone[item.valueTone]}`}>{item.value}</p>
              <span
                className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  item.isNow ? "bg-emerald-400/10 text-emerald-400" : "bg-white/5 text-zinc-400"
                }`}
              >
                {item.when}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
