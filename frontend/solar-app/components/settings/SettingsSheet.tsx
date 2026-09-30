"use client";

import { ReactNode, useEffect, useRef, useState } from "react";
import { useSWRConfig } from "swr";
import { FontScale, useFontScale, useStatus } from "@/hooks/useSettings";
import { apiUrl } from "@/lib/api";
import { SyncStartResponse } from "@/lib/types/system";
import {
  RESERVE_MAX_PCT,
  RESERVE_MIN_PCT,
  RESERVE_STEP_PCT,
  clampReserve,
  evnLine,
  forecastLine,
  historyLine,
  syncSummary,
} from "./settings.helpers";

const FONT_SCALES: { value: FontScale; label: string }[] = [
  { value: "1", label: "Normal" },
  { value: "lg", label: "Large" },
  { value: "xl", label: "Extra large" },
];

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="border-t border-white/5 py-4 first:border-t-0 first:pt-1">
      <h3 className="text-[13px] font-semibold text-zinc-100">{title}</h3>
      {hint && <p className="mt-0.5 text-[12px] leading-snug text-zinc-500">{hint}</p>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

const segmentButton = (on: boolean) =>
  `flex-1 rounded-full px-3 py-2 text-[13px] font-semibold transition-colors ${
    on ? "bg-white/15 text-zinc-50" : "text-zinc-400 hover:text-zinc-200"
  }`;

function ReserveControl({ saved }: { saved: number }) {
  const { mutate } = useSWRConfig();
  const [draft, setDraft] = useState<number | null>(null);
  const [state, setState] = useState<"idle" | "saving" | "error">("idle");
  const value = draft ?? saved;
  const dirty = draft !== null && draft !== saved;

  const save = async () => {
    setState("saving");
    try {
      const response = await fetch(apiUrl("/api/action"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: "set_reserve", params: { reserve_pct: value } }),
      });
      if (!(await response.json())?.ok) throw new Error("rejected");
      await Promise.all([mutate(apiUrl("/api/status")), mutate(apiUrl("/api/metrics"))]);
      setDraft(null);
      setState("idle");
    } catch {
      setState("error");
    }
  };

  const step = (delta: number) => {
    setDraft(clampReserve(value + delta));
    setState("idle");
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <button
          aria-label="Lower reserve"
          className="grid size-10 place-items-center rounded-full bg-white/5 text-zinc-200 disabled:opacity-30"
          disabled={value <= RESERVE_MIN_PCT}
          onClick={() => step(-RESERVE_STEP_PCT)}
          type="button"
        >
          <i className="fa-solid fa-minus" />
        </button>
        <output aria-live="polite" className="min-w-16 text-center text-[24px] font-light tabular-nums text-[#b8a6ff]">
          {value}%
        </output>
        <button
          aria-label="Raise reserve"
          className="grid size-10 place-items-center rounded-full bg-white/5 text-zinc-200 disabled:opacity-30"
          disabled={value >= RESERVE_MAX_PCT}
          onClick={() => step(RESERVE_STEP_PCT)}
          type="button"
        >
          <i className="fa-solid fa-plus" />
        </button>
        {dirty && (
          <button
            className="ml-auto rounded-full bg-[#ffc76b] px-4 py-2 text-[13px] font-semibold text-[#04060c] disabled:opacity-60"
            disabled={state === "saving"}
            onClick={save}
            type="button"
          >
            {state === "saving" ? "Saving…" : "Save"}
          </button>
        )}
      </div>
      {state === "error" && <p className="text-[12px] text-[#fb8a95]">Couldn&apos;t save — try again.</p>}
    </div>
  );
}

function DataControls({ active }: { active: boolean }) {
  const { data: status, error, mutate } = useStatus(active);
  const [message, setMessage] = useState<string | null>(null);
  const summary = status ? syncSummary(status.sync) : error ? "Sync status unavailable." : "…";

  const syncNow = async () => {
    setMessage(null);
    try {
      const response = await fetch(apiUrl("/api/sync"), { method: "POST" });
      const body: SyncStartResponse = await response.json();
      if (!body.ok) {
        setMessage(body.reason === "too_soon" ? `Just synced — try again in ${body.retry_in}s.` : "A sync is already running.");
      }
    } catch {
      setMessage("Couldn't reach the server.");
    }
    mutate();
  };

  return (
    <div className="flex flex-col gap-3">
      <p className="text-[12px] text-zinc-400" role="status">
        {summary}
        {message && <span className="block text-[#ffc76b]">{message}</span>}
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          className="rounded-full bg-white/5 px-4 py-2 text-[13px] font-semibold text-zinc-100 ring-1 ring-inset ring-white/10 disabled:opacity-40"
          disabled={!status?.sync.supported || status.sync.running}
          onClick={syncNow}
          type="button"
        >
          <i className={`fa-solid fa-rotate mr-1.5 ${status?.sync.running ? "animate-spin" : ""}`} />
          Sync now
        </button>
        <a
          className="rounded-full bg-white/5 px-4 py-2 text-[13px] font-semibold text-zinc-100 ring-1 ring-inset ring-white/10"
          download
          href={apiUrl("/api/export.csv")}
        >
          <i className="fa-solid fa-download mr-1.5" />
          Export CSV
        </a>
      </div>
    </div>
  );
}

function SystemList({ active }: { active: boolean }) {
  const { data: status, error } = useStatus(active);
  if (error) return <p className="text-[12px] text-[#fb8a95]">Couldn&apos;t load the system status from the backend.</p>;
  if (!status) return <p className="text-[12px] text-zinc-500">Loading…</p>;

  const rows: [string, string][] = [
    ["Data source", `${status.source}${status.live ? ` · ${status.live}` : ""}`],
    ["History", historyLine(status.history)],
    ["EVN portal", evnLine(status.evn)],
    ["Forecast model", forecastLine(status.forecast)],
    ["Assistant", status.assistant ? "On" : "Off (no API key)"],
  ];
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[12px]">
      {rows.map(([label, value]) => (
        <div className="contents" key={label}>
          <dt className="text-zinc-500">{label}</dt>
          <dd className="text-right text-zinc-200">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function SettingsSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [scale, setScale] = useFontScale();
  const { data: status } = useStatus(open);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      aria-labelledby="settings-title"
      className="mx-auto mb-0 mt-auto max-h-[88dvh] w-full max-w-none overflow-y-auto rounded-t-[26px] border border-white/10 bg-[#0b0f1a] p-5 pb-[calc(20px+env(safe-area-inset-bottom,0px))] text-zinc-100 shadow-2xl transition-[translate,opacity] duration-200 backdrop:bg-black/60 backdrop:backdrop-blur-sm starting:translate-y-8 starting:opacity-0 motion-reduce:transition-none sm:m-auto sm:max-w-md sm:rounded-[26px] sm:pb-5"
      onClick={(event) => event.target === event.currentTarget && onClose()}
      onClose={onClose}
      ref={dialogRef}
    >
      <div className="mx-auto -mt-1 mb-3 h-1 w-10 rounded-full bg-white/15 sm:hidden" aria-hidden="true" />
      <div className="flex items-center justify-between">
        <h2 className="text-[15px] font-bold" id="settings-title">
          <i className="fa-solid fa-gear mr-2 text-zinc-400" />
          Settings
        </h2>
        <button
          aria-label="Close"
          className="grid size-8 place-items-center rounded-full text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
          onClick={onClose}
          type="button"
        >
          <i className="fa-solid fa-xmark" />
        </button>
      </div>

      <div className="mt-3">
        <Section hint="Makes every page bigger and easier to read." title="Text size">
          <div className="flex gap-1 rounded-full bg-white/5 p-1" role="group" aria-label="Text size">
            {FONT_SCALES.map((item) => (
              <button
                aria-pressed={scale === item.value}
                className={segmentButton(scale === item.value)}
                key={item.value}
                onClick={() => setScale(item.value)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
        </Section>

        <Section
          hint="Battery kept for outages. Used in the dashboard's estimates only — nothing is written to the inverter."
          title="Battery reserve"
        >
          {status ? <ReserveControl key={status.battery_reserve_percent} saved={status.battery_reserve_percent} /> : null}
        </Section>

        <Section hint="History syncs from SEMS on startup and every 12 hours." title="Data">
          <DataControls active={open} />
        </Section>

        <Section title="System">
          <SystemList active={open} />
        </Section>
      </div>
    </dialog>
  );
}
