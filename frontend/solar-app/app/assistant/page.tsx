"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";
import DashboardShell from "@/components/DashboardShell";
import ChatComposer from "@/components/assistant/ChatComposer";
import ChatLog from "@/components/assistant/ChatLog";
import NoticeList from "@/components/assistant/NoticeList";
import SuggestedQuestions from "@/components/assistant/SuggestedQuestions";
import { useAiStatus, useChat, useNotices } from "@/hooks/useAssistant";
import { useMetrics } from "@/hooks/useOptimization";
import { MetricsResponse } from "@/lib/types";
import { Notice } from "@/lib/types/assistant";
import { greeting } from "./assistant.helpers";

const noSubscription = () => () => {};

function useIsClient(): boolean {
  return useSyncExternalStore(noSubscription, () => true, () => false);
}

interface ChatPanelProps {
  metrics: MetricsResponse | undefined;
  notices: Notice[];
  onDismissNotice: (id: number) => void;
}

function ChatPanel({ metrics, notices, onDismissNotice }: ChatPanelProps) {
  const { entries, live, busy, send, applyAction, dismissAction, clear } = useChat();
  const started = entries.length > 0 || busy;
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (started) endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [started, entries.length, live?.text, live?.status]);

  return (
    <>
      <NoticeList notices={notices} onAsk={send} onDismiss={onDismissNotice} />

      <section aria-labelledby="chat-title" className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-zinc-100" id="chat-title">
            <i className="fa-solid fa-robot mr-1.5 text-[#ffc76b]" />
            Ask the assistant
          </h2>
          {entries.length > 0 && (
            <button
              className="rounded-full bg-white/5 px-3 py-1 text-[11px] font-semibold text-zinc-400 hover:text-zinc-200 disabled:opacity-40"
              disabled={busy}
              onClick={clear}
              type="button"
            >
              <i className="fa-solid fa-rotate-left mr-1" />
              New chat
            </button>
          )}
        </div>
        <ChatLog
          entries={entries}
          greeting={greeting(metrics)}
          live={live}
          onApply={applyAction}
          onDismiss={dismissAction}
        />
        {!started && <SuggestedQuestions onAsk={send} variant="cards" />}
        <div ref={endRef} />
      </section>

      <ChatComposer
        above={started && !busy ? <SuggestedQuestions onAsk={send} variant="chips" /> : null}
        busy={busy}
        onSend={send}
      />
    </>
  );
}

export default function AssistantPage() {
  const isClient = useIsClient();
  const { data: ai, error: aiError } = useAiStatus();
  const { data: noticeData, dismiss } = useNotices();
  const { data: metrics, error: metricsError } = useMetrics();
  const notices = noticeData?.notices ?? [];

  if (aiError && metricsError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#04060c] font-sans text-red-400">
        Can&apos;t get data from Backend
      </div>
    );
  }

  return (
    <DashboardShell source="" status={metricsError ? "error" : "online"}>
      {isClient && ai?.enabled ? (
        <ChatPanel metrics={metrics} notices={notices} onDismissNotice={dismiss} />
      ) : (
        <>
          <NoticeList notices={notices} onDismiss={dismiss} />
          {ai && !ai.enabled && (
            <section className="rounded-[22px] border border-white/10 bg-[#0a0e18]/90 p-4 text-[13px] leading-relaxed text-zinc-400">
              <p className="font-semibold text-zinc-200">
                <i className="fa-solid fa-robot mr-1.5 text-zinc-500" />
                The chat assistant is off
              </p>
              <p className="mt-1">
                Add <code className="text-zinc-300">ai.api_key</code> to <code className="text-zinc-300">config.json</code> and
                restart the backend to turn it on. Notices keep working without it.
              </p>
            </section>
          )}
        </>
      )}
    </DashboardShell>
  );
}
