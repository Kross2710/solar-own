"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import DashboardPage from "@/components/DashboardPage";
import Card from "@/components/Card";
import { apiUrl, fetcher } from "@/lib/api";
import { AccuracyResponse } from "@/lib/types/optimization";

export default function AccuracyPage() {
  const [model, setModel] = useState("");
  const { data, error, isLoading, isValidating, mutate } = useSWR<AccuracyResponse>(apiUrl(`/api/forecast/accuracy${model ? `?model=${encodeURIComponent(model)}` : ""}`), fetcher, { refreshInterval: 30_000 });
  const ready = data?.ready ? data : null;
  const points = ready?.points ?? [];
  const min = Math.min(0, ...points.map(p => Math.min(p.actual, p.pred, p.baseline_pred)));
  const max = Math.max(1, ...points.map(p => Math.max(p.actual, p.pred, p.baseline_pred)));
  const x = (i: number) => 55 + i * 900 / Math.max(1, points.length - 1);
  const y = (value: number) => 280 - (value - min) * 240 / (max - min);
  const line = (key: "actual" | "pred" | "baseline_pred") => points.map((p, i) => `${x(i)},${y(p[key])}`).join(" ");

  return <DashboardPage refreshing={isValidating && Boolean(data)} status={error ? "error" : isLoading ? "connecting" : "online"}>
    <Link href="/optimization" className="text-sm text-pv">← Optimization</Link>
    <Card accent="pv">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-lg font-bold">Forecast accuracy</h1>
        {ready && <label className="text-xs text-zinc-400">Model <select aria-label="Forecast model" value={model || ready.model} onChange={e => setModel(e.target.value)} className="ml-2 max-w-full rounded-lg bg-ink p-2 text-zinc-100">
          {ready.models.map(name => <option key={name} value={name}>{name}</option>)}
        </select></label>}
      </div>
      <p className="mt-3 text-sm text-zinc-400">Historical backtest: each prediction learns only from earlier days. These dates also select the model, so these scores are not independent live accuracy measurements.</p>
      <p className="mt-2 text-xs text-zinc-500">Output is limited by home load and battery room. Baseline: the average of all earlier days. Historical weather can be more accurate than tomorrow’s weather forecast.</p>
      {isLoading && <p className="mt-6" role="status">Calculating backtest…</p>}
      {error && <div className="mt-6" role="alert">Could not load accuracy. <button className="text-pv underline" onClick={() => void mutate()}>Retry</button></div>}
      {data && !data.ready && <p className="mt-6" role="status">Forecast is not ready yet. This page refreshes automatically.</p>}
      {ready && <>
        <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[["MAE", `${ready.mae.toFixed(2)} kWh/day`], ["Baseline MAE", `${ready.baseline_mae.toFixed(2)} kWh/day`], ["Skill vs baseline", ready.skill_vs_baseline == null ? "—" : `${(ready.skill_vs_baseline * 100).toFixed(1)}%`], ["R²", ready.r2.toFixed(3)]].map(([label, value]) => <div key={label} className="rounded-xl bg-white/5 p-3"><p className="text-xs text-zinc-400">{label}</p><p className="mt-1 font-bold tabular-nums">{value}</p></div>)}
        </div>
        <p className="mt-3 text-xs text-zinc-400">RMSE {ready.rmse} kWh · bias {ready.bias} kWh · MAPE {ready.mape}% · {ready.n_test} tested days after {ready.warmup} warm-up days · {ready.n_train} total days</p>
        {points.length > 0 && <>
          <div className="mt-5 overflow-x-auto">
            <svg viewBox="0 0 1000 320" className="min-w-[580px] w-full" role="img" aria-label={`Actual, predicted and baseline output from ${points[0].day} to ${points.at(-1)!.day}`}>
              {[0, .25, .5, .75, 1].map(f => <g key={f}><line x1="55" x2="955" y1={y(min + (max - min) * f)} y2={y(min + (max - min) * f)} stroke="currentColor" opacity=".12"/><text x="48" y={y(min + (max - min) * f) + 4} textAnchor="end" fill="#a1a1aa" fontSize="12">{(min + (max - min) * f).toFixed(0)}</text></g>)}
              <polyline points={line("baseline_pred")} fill="none" stroke="#a1a1aa" strokeWidth="2" strokeDasharray="6 5"/>
              <polyline points={line("actual")} fill="none" stroke="#ffc76b" strokeWidth="2"/>
              <polyline points={line("pred")} fill="none" stroke="#7dd3fc" strokeWidth="2"/>
              {points.map((p,i) => <circle key={p.day} cx={x(i)} cy={y(p.pred)} r="4" fill="transparent"><title>{p.day}: actual {p.actual}, predicted {p.pred}, baseline {p.baseline_pred} kWh</title></circle>)}
              <text x="55" y="308" fill="#a1a1aa" fontSize="12">{points[0].day}</text><text x="955" y="308" fill="#a1a1aa" fontSize="12" textAnchor="end">{points.at(-1)!.day}</text>
            </svg>
          </div>
          <p className="text-xs"><span className="text-pv">Actual</span> · <span className="text-sky-300">Predicted</span> · <span className="text-zinc-400">Earlier-days average</span> · kWh/day</p>
          <details className="mt-4 text-xs text-zinc-400"><summary className="cursor-pointer">Daily values</summary><div className="mt-3 max-h-80 overflow-auto"><table className="w-full text-left tabular-nums"><thead><tr><th scope="col">Day</th><th scope="col">Actual</th><th scope="col">Predicted</th><th scope="col">Baseline</th></tr></thead><tbody>{points.map(p => <tr key={p.day}><th scope="row" className="py-1 font-normal">{p.day}</th><td>{p.actual}</td><td>{p.pred}</td><td>{p.baseline_pred}</td></tr>)}</tbody></table></div></details>
        </>}
      </>}
    </Card>
  </DashboardPage>;
}
