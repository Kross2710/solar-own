"use client";

import { useId, useState, type ReactNode } from "react";

export default function DetailsDisclosure({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  return (
    <>
      <div
        id={panelId}
        className={`grid transition-[grid-template-rows,margin] duration-300 ease-out motion-reduce:transition-none ${
          open ? "mt-3 grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
        inert={!open}
      >
        <div className="overflow-hidden">{children}</div>
      </div>

      <div className="mt-3 text-center">
        <button
          type="button"
          className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-1 text-[11.5px] font-semibold text-zinc-400 transition-colors hover:border-zinc-500 hover:bg-white/[0.06] hover:text-zinc-100 aria-expanded:border-zinc-500 aria-expanded:text-zinc-100"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Collapse ▴" : "See details ▾"}
        </button>
      </div>
    </>
  );
}
