"use client";

import { useState } from "react";
import { noticeView } from "@/app/assistant/assistant.helpers";
import { Notice } from "@/lib/types/assistant";

// More than this and the chat gets pushed off screen; the rest sit behind "Show more".
const VISIBLE_NOTICES = 2;

const tone = {
  warn: "bg-[#fb8a95]/10 text-[#fb8a95] ring-[#fb8a95]/35",
  info: "bg-[#ffc76b]/10 text-[#ffc76b] ring-[#ffc76b]/35",
};

interface NoticeListProps {
  notices: Notice[];
  onDismiss: (id: number) => void;
  onAsk?: (prompt: string) => void;
}

export default function NoticeList({ notices, onDismiss, onAsk }: NoticeListProps) {
  const [expanded, setExpanded] = useState(false);
  if (!notices.length) return null;

  const shown = expanded ? notices : notices.slice(0, VISIBLE_NOTICES);
  const hidden = notices.length - shown.length;

  return (
    <section aria-labelledby="notices" className="flex flex-col gap-2">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-500" id="notices">
        Noticed for you
      </h2>
      <ul className="flex flex-col gap-2">
        {shown.map((notice) => {
          const view = noticeView(notice);
          return (
            <li
              className="flex gap-3 rounded-[18px] border border-white/10 bg-[#0a0e18]/90 p-3 shadow-xl backdrop-blur-xl"
              key={notice.id}
            >
              <span className={`grid size-9 shrink-0 place-items-center rounded-xl ring-1 ring-inset ${tone[notice.severity]}`}>
                <i className={`fa-solid ${view.icon}`} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-semibold leading-snug text-zinc-100">{view.title}</p>
                <p className="mt-0.5 text-[12px] leading-snug text-zinc-400">{view.detail}</p>
                {onAsk && (
                  <button
                    className="mt-2 rounded-full bg-white/5 px-2.5 py-1 text-[11px] font-semibold text-[#ffc76b] ring-1 ring-inset ring-[#ffc76b]/25 transition-colors hover:bg-[#ffc76b]/10"
                    onClick={() => onAsk(view.ask)}
                    type="button"
                  >
                    <i className="fa-solid fa-comment-dots mr-1" />
                    Ask about this
                  </button>
                )}
              </div>
              <button
                aria-label={`Dismiss: ${view.title}`}
                className="grid size-7 shrink-0 place-items-center rounded-full text-zinc-500 transition-colors hover:bg-white/5 hover:text-zinc-200"
                onClick={() => onDismiss(notice.id)}
                type="button"
              >
                <i className="fa-solid fa-xmark text-[13px]" />
              </button>
            </li>
          );
        })}
      </ul>
      {(hidden > 0 || expanded) && notices.length > VISIBLE_NOTICES && (
        <button
          aria-expanded={expanded}
          className="self-start rounded-full bg-white/5 px-3 py-1 text-[11px] font-semibold text-zinc-300"
          onClick={() => setExpanded((open) => !open)}
          type="button"
        >
          {expanded ? "Show less ▴" : `Show ${hidden} more ▾`}
        </button>
      )}
    </section>
  );
}
