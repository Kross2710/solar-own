interface StatCard {
  label: string;
  value: string;
  detail: string;
}

export default function HistoryStatGrid({ items }: { items: StatCard[] }) {
  return (
    <div className="mt-3 grid grid-cols-2 gap-2">
      {items.map(({ label, value, detail }) => (
        <article className="rounded-xl border border-white/10 bg-black/10 p-3" key={label}>
          <p className="text-[11px] text-zinc-400">{label}</p>
          <p className="mt-1 text-lg font-bold leading-none tabular-nums text-zinc-100">{value}</p>
          <p className="mt-1 text-[11px] leading-snug text-zinc-400">{detail}</p>
        </article>
      ))}
    </div>
  );
}