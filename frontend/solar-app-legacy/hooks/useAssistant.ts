import { useCallback, useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { entryId, errorText, parseSse, toApiMessages } from "@/app/assistant/assistant.helpers";
import { apiUrl, fetcher } from "@/lib/api";
import { AiStatusResponse, ChatEntry, NoticesResponse } from "@/lib/types/assistant";

const MINUTE = 60 * 1000;
const CHAT_STORAGE_KEY = "chat.v1";
const MAX_STORED_ENTRIES = 40;

export function useAiStatus() {
  return useSWR<AiStatusResponse>(apiUrl("/api/ai_status"), fetcher, {
    refreshInterval: 30 * MINUTE,
    revalidateOnFocus: false,
  });
}

export function useNotices() {
  const swr = useSWR<NoticesResponse>(apiUrl("/api/notices"), fetcher, { refreshInterval: 10 * MINUTE });
  const { mutate } = swr;

  const dismiss = useCallback(
    async (id: number) => {
      await mutate(
        async (current) => {
          await fetch(apiUrl(`/api/notices/${id}/dismiss`), { method: "POST" });
          return { notices: (current?.notices ?? []).filter((notice) => notice.id !== id) };
        },
        { revalidate: false },
      );
    },
    [mutate],
  );

  return { ...swr, dismiss };
}

function loadEntries(): ChatEntry[] {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    // Earlier versions stored setting proposals alongside messages.
    return Array.isArray(parsed) ? parsed.filter(entry => entry?.type === "message") : [];
  } catch {
    return [];
  }
}

export interface LiveReply {
  text: string;
  status: string | null;
}

// Must be used by a component that only renders on the client (reads localStorage on init).
export function useChat() {
  const [entries, setEntries] = useState<ChatEntry[]>(loadEntries);
  const [live, setLive] = useState<LiveReply | null>(null);
  const entriesRef = useRef(entries);
  const busyRef = useRef(false);

  useEffect(() => {
    entriesRef.current = entries;
    try {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(entries.slice(-MAX_STORED_ENTRIES)));
    } catch {
      // Storage full or disabled: the chat still works for this session.
    }
  }, [entries]);

  const send = useCallback(async (raw: string) => {
    const text = raw.trim();
    if (!text || busyRef.current) return;
    busyRef.current = true;

    const history: ChatEntry[] = [...entriesRef.current, { id: entryId(), type: "message", role: "user", content: text }];
    entriesRef.current = history;
    setEntries(history);
    setLive({ text: "", status: null });

    let reply = "";
    let errorCode: string | null = null;
    try {
      const response = await fetch(apiUrl("/api/chat"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: toApiMessages(history), lang: "en" }),
      });
      const isStream = (response.headers.get("Content-Type") ?? "").includes("text/event-stream");
      if (!isStream || !response.body) {
        const body = await response.json().catch(() => null);
        errorCode = body?.enabled === false ? "disabled" : (body?.error_code ?? "assistant_error");
      } else {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parsed = parseSse(buffer);
          buffer = parsed.rest;
          for (const event of parsed.events) {
            if (event.type === "delta") {
              reply += event.text;
              setLive({ text: reply, status: null });
            } else if (event.type === "status") {
              setLive({ text: reply, status: event.tool });
            } else if (event.type === "error") {
              errorCode = event.error_code || "assistant_error";
            }
          }
        }
      }
    } catch {
      // Connection dropped mid-reply: keep what arrived.
      if (!reply) errorCode = "network";
    }

    const added: ChatEntry[] = reply
      ? [{ id: entryId(), type: "message", role: "assistant", content: reply }]
      : [{
          id: entryId(), type: "message", role: "assistant", error: true,
          content: errorCode === "disabled" ? "The assistant isn't enabled (missing API key)." : errorText(errorCode),
        }];
    setEntries((current) => [...current, ...added]);
    setLive(null);
    busyRef.current = false;
  }, []);

  const clear = useCallback(() => {
    if (busyRef.current) return;
    setEntries([]);
  }, []);

  return { entries, live, busy: live !== null, send, clear };
}
