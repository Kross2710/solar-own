"use client";

import DashboardPage from "@/components/DashboardPage";
import EvnBillCard from "@/components/money/EvnBillCard";
import SavingsCards from "@/components/money/SavingsCards";
import SavingsHero from "@/components/money/SavingsHero";
import TierLadderCard from "@/components/money/TierLadderCard";
import { useMoney } from "@/hooks/useMoney";

export default function MoneyPage() {
  const { money, error, isLoading } = useMoney();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink font-sans text-zinc-400">
        Connecting to Solar...
      </div>
    );
  }

  if (error || !money) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink font-sans text-grid-in">
        Can&apos;t get data from Backend
      </div>
    );
  }

  return (
    <DashboardPage status="online" source="">
      <div className="grid gap-7 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] xl:items-center">
        <SavingsHero cycle={money.cycle} />
        <SavingsCards
          today={money.today}
          cycle={money.cycle}
          total={money.total}
          payback={money.payback}
        />
      </div>
      <div className="grid gap-7 xl:grid-cols-2 xl:items-start">
        <EvnBillCard
          cycle={money.cycle}
          prevCycle={money.prev_cycle}
          tier={money.tier}
          evnBill={money.evn_bill}
          history={money.evn_history ?? []}
          solarStart={money.solar_start ?? null}
        />
        <div>
          <TierLadderCard tier={money.tier} billNow={money.cycle.bill_now} />
          {money.tariff && <p className="mt-3 text-xs text-zinc-400">{money.tariff.label} · effective {money.tariff.effective_from} · VAT {Math.round(money.tariff.vat * 100)}% included{money.tariff.mixed ? " · transition cycle: estimated allocation by days" : ""}</p>}
        </div>
      </div>
    </DashboardPage>
  );
}
