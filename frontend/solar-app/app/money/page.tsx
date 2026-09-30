"use client";

import DashboardShell from "@/components/DashboardShell";
import EvnBillCard from "@/components/money/EvnBillCard";
import SavingsCards from "@/components/money/SavingsCards";
import SavingsHero from "@/components/money/SavingsHero";
import TierLadderCard from "@/components/money/TierLadderCard";
import { useMoney } from "@/hooks/useMoney";

export default function MoneyPage() {
  const { money, error, isLoading } = useMoney();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#04060c] font-sans text-zinc-400">
        Connecting to Solar...
      </div>
    );
  }

  if (error || !money) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#04060c] font-sans text-red-400">
        Can&apos;t get data from Backend
      </div>
    );
  }

  return (
    <DashboardShell status="online" source="">
      <SavingsHero cycle={money.cycle} />
      <SavingsCards
        today={money.today}
        cycle={money.cycle}
        total={money.total}
        payback={money.payback}
      />
      <EvnBillCard
        cycle={money.cycle}
        prevCycle={money.prev_cycle}
        tier={money.tier}
        evnBill={money.evn_bill}
        history={money.evn_history ?? []}
        solarStart={money.solar_start ?? null}
      />
      <TierLadderCard tier={money.tier} billNow={money.cycle.bill_now} />
    </DashboardShell>
  );
}
