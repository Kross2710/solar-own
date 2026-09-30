"use client";

import { FormEvent, ReactNode, useState } from "react";

interface ChatComposerProps {
  busy: boolean;
  onSend: (text: string) => void;
  above?: ReactNode;
}

// Sticks above the fixed bottom nav on phones (see .nav in globals.css), to the bottom on desktop.
export default function ChatComposer({ busy, onSend, above }: ChatComposerProps) {
  const [text, setText] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!text.trim() || busy) return;
    onSend(text);
    setText("");
  };

  return (
    <div className="sticky bottom-[calc(76px+env(safe-area-inset-bottom,0px))] z-40 -mx-1 flex flex-col gap-2 bg-gradient-to-t from-[#04060c] via-[#04060c]/95 to-transparent px-1 pb-1 pt-4 sm:bottom-4">
      {above}
      <form className="flex gap-2" onSubmit={submit}>
        <input
          aria-label="Ask about your home's power"
          autoComplete="off"
          className="min-w-0 flex-1 rounded-full border border-white/10 bg-white/[0.06] px-4 py-2.5 text-[16px] text-zinc-100 placeholder:text-zinc-500 focus:border-[#ffc76b]/50 focus:outline-none"
          maxLength={2000}
          onChange={(event) => setText(event.target.value)}
          placeholder="Ask about your home's power…"
          value={text}
        />
        <button
          aria-label="Send"
          className="grid size-11 shrink-0 place-items-center rounded-full bg-[#ffc76b] text-[15px] text-[#04060c] transition active:scale-90 disabled:opacity-40"
          disabled={busy || !text.trim()}
          type="submit"
        >
          <i className={`fa-solid ${busy ? "fa-ellipsis" : "fa-paper-plane"}`} />
        </button>
      </form>
    </div>
  );
}
