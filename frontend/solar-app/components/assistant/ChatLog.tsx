import { ACTION_NOTE, actionLabel, toolLabel } from "@/app/assistant/assistant.helpers";
import { LiveReply } from "@/hooks/useAssistant";
import { ChatEntry } from "@/lib/types/assistant";

const bubble = "max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed";
const aiBubble = `${bubble} self-start rounded-bl-md border border-white/10 bg-white/[0.05] text-zinc-100`;

function ActionCard({
  entry,
  onApply,
  onDismiss,
}: {
  entry: ChatEntry & { type: "action" };
  onApply: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  const { action, state } = entry;
  const pct = action.params.reserve_pct;

  return (
    <div className={`${aiBubble} flex flex-col gap-1.5 whitespace-normal`}>
      <p className="font-semibold">
        <i className="fa-solid fa-sliders mr-1.5 text-[#ffc76b]" />
        {actionLabel(action)}
      </p>
      {action.reason && <p className="text-[13px] text-zinc-300">{action.reason}</p>}
      <p className="text-[11px] text-zinc-500">{ACTION_NOTE}</p>
      {state === "pending" || state === "applying" ? (
        <div className="mt-1 flex gap-2">
          <button
            className="rounded-full bg-[#ffc76b] px-4 py-1.5 text-[13px] font-semibold text-[#04060c] disabled:opacity-60"
            disabled={state === "applying"}
            onClick={() => onApply(entry.id)}
            type="button"
          >
            {state === "applying" ? "Applying…" : "Apply"}
          </button>
          <button
            className="rounded-full border border-white/10 px-4 py-1.5 text-[13px] text-zinc-400"
            disabled={state === "applying"}
            onClick={() => onDismiss(entry.id)}
            type="button"
          >
            Dismiss
          </button>
        </div>
      ) : (
        <p className={`text-[13px] ${state === "failed" ? "text-[#fb8a95]" : "text-emerald-400"}`} role="status">
          {state === "applied" && `Done — battery reserve is now ${pct}%.`}
          {state === "dismissed" && "Suggestion dismissed."}
          {state === "failed" && "Couldn't apply the change — try again later."}
        </p>
      )}
    </div>
  );
}

interface ChatLogProps {
  greeting: string;
  entries: ChatEntry[];
  live: LiveReply | null;
  onApply: (id: string) => void;
  onDismiss: (id: string) => void;
}

export default function ChatLog({ greeting, entries, live, onApply, onDismiss }: ChatLogProps) {
  return (
    <div className="flex flex-col gap-2.5" aria-live="polite" aria-busy={live !== null}>
      <p className={aiBubble}>{greeting}</p>
      {entries.map((entry) => {
        if (entry.type === "action") {
          return <ActionCard entry={entry} key={entry.id} onApply={onApply} onDismiss={onDismiss} />;
        }
        if (entry.role === "user") {
          return (
            <p className={`${bubble} self-end rounded-br-md bg-[#ffc76b] text-[#04060c]`} key={entry.id}>
              {entry.content}
            </p>
          );
        }
        return (
          <p className={`${aiBubble} ${entry.error ? "text-zinc-400 italic" : ""}`} key={entry.id}>
            {entry.content}
          </p>
        );
      })}
      {live &&
        (live.text ? (
          <p className={aiBubble}>{live.text}</p>
        ) : (
          <p className={`${aiBubble} text-zinc-400`}>
            {live.status ? (
              <span className="italic">
                <i className="fa-solid fa-magnifying-glass mr-1.5 text-[#7dd3fc]" />
                {toolLabel(live.status)}
              </span>
            ) : (
              <span className="inline-flex gap-1" aria-label="Thinking">
                {[0, 150, 300].map((delay) => (
                  <span className="size-1.5 animate-bounce rounded-full bg-zinc-400" key={delay} style={{ animationDelay: `${delay}ms` }} />
                ))}
              </span>
            )}
          </p>
        ))}
    </div>
  );
}
