import Card from "@/components/Card";

export default function SelfPoweredCard( {selfPoweredDays, selfPoweredDates, avgSelfPowered} : {selfPoweredDays: number[], selfPoweredDates: string[], avgSelfPowered: number} ) {
  return (
    <Card accent="good">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-zinc-100">
          <i className="fa-solid fa-leaf mr-1 text-good" />
          Self-powered · 30 days
        </h2>
        <span className="text-xs font-bold text-good">avg {avgSelfPowered}%</span>
      </div>

      <div className="mt-4 grid grid-cols-[repeat(15,minmax(0,1fr))] gap-1.5 xl:grid-cols-[repeat(30,minmax(0,1fr))] xl:gap-1">
        {selfPoweredDays.map((value, index) => (
          <span
            key={index}
            className={`h-5 rounded-[3px] xl:h-8 ${
              value < 50
                ? "bg-pv/40"
                : value >= 85
                ? "bg-good/90"
                : value >= 75
                ? "bg-good/70"
                : "bg-good/50"
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
    </Card>
  );
}