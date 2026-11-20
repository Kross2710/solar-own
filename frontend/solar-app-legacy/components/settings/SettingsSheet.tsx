"use client";

import { ReactNode, useEffect, useRef, useState } from "react";
import UpdatedAgo from "@/components/overview/UpdatedAgo";
import { FontScale, useFontScale, useStatus } from "@/hooks/useSettings";
import { apiUrl } from "@/lib/api";
import { SyncStartResponse } from "@/lib/types/system";
import {
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
        {message && <span className="block text-pv">{message}</span>}
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
  if (error) return <p className="text-[12px] text-grid-in">Couldn&apos;t load the system status from the backend.</p>;
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

export default function SettingsSheet({ open, onClose, updatedAt }: { open: boolean; onClose: () => void; updatedAt?: string }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [scale, setScale] = useFontScale();

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

        <Section hint="History syncs from SEMS on startup and every 12 hours." title="Data">
          <DataControls active={open} />
        </Section>

        <Section title="System">
          <div className="mb-2 flex justify-between gap-4 text-[12px]">
            <span className="text-zinc-500">Latest inverter reading</span>
            {open && updatedAt ? <UpdatedAgo iso={updatedAt} /> : <span>—</span>}
          </div>
          <SystemList active={open} />
        </Section>
      </div>
    </dialog>
  );
}
