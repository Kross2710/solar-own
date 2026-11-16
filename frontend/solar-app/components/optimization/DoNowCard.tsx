import { Suggestion, SuggestionTone } from "@/app/optimization/optimization.helpers";
import Card from "@/components/Card";

const iconTone: Record<SuggestionTone, string> = {
  load: "bg-load/10 text-load ring-load/35",
  batt: "bg-batt/10 text-batt ring-batt/35",
  warn: "bg-grid-in/10 text-grid-in ring-grid-in/35",
};

const valueTone: Record<Suggestion["valueTone"], string> = {
  good: "text-good",
  bad: "text-grid-in",
  neutral: "text-zinc-200",
};

export default function DoNowCard({ suggestions }: { suggestions: Suggestion[] }) {
  if (!suggestions.length) return null;

  return (
    <Card
      accent="load"
      aria-labelledby="do-now"
    >
      <h2 className="text-sm font-bold text-zinc-100" id="do-now">
        <i className="fa-solid fa-bolt mr-1.5 text-load" />
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
                  item.isNow ? "bg-good/10 text-good" : "bg-white/5 text-zinc-400"
                }`}
              >
                {item.when}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
