export default function SelfPoweredCard( {selfPoweredDays, selfPoweredDates, avgSelfPowered} : {selfPoweredDays: number[], selfPoweredDates: string[], avgSelfPowered: number} ) {
  return (
    <section className="rounded-[22px] border border-white/10 border-t-emerald-300/25 bg-[#0a0e18]/90 p-3 shadow-2xl backdrop-blur-xl sm:p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-zinc-100">
          <i className="fa-solid fa-leaf mr-1 text-emerald-400" />
          Self-powered · 30 days
        </h2>
        <span className="text-xs font-bold text-emerald-400">avg {avgSelfPowered}%</span>
      </div>

      <div className="mt-4 grid grid-cols-[repeat(15,minmax(0,1fr))] gap-1.5">
        {selfPoweredDays.map((value, index) => (
          <span
            key={index}
            className={`h-5 rounded-[3px] ${
              value < 50
                ? "bg-amber-300/40"
                : value >= 85
                ? "bg-emerald-300/90"
                : value >= 75
                ? "bg-emerald-300/70"
                : "bg-emerald-300/50"
            }`}
            title={`Day ${index + 1}: ${value}% self-powered`}
          />
        ))}
      </div>

      <div className="mt-2 flex justify-between gap-3 text-[10px] text-zinc-500">
        <span>{selfPoweredDates[0]}</span>
        <span>yellow = rainy day, more grid</span>
        <span>{selfPoweredDates[1]}</span>
      </div>
    </section>
  );
}