import { toolLabel } from "@/app/assistant/assistant.helpers";
import { LiveReply } from "@/hooks/useAssistant";
import { ChatEntry } from "@/lib/types/assistant";

const bubble = "max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed";
const aiBubble = `${bubble} self-start rounded-bl-md border border-white/10 bg-white/[0.05] text-zinc-100`;

interface ChatLogProps {
  greeting: string;
  entries: ChatEntry[];
  live: LiveReply | null;
}

export default function ChatLog({ greeting, entries, live }: ChatLogProps) {
  return (
    <div className="flex flex-col gap-2.5" aria-live="polite" aria-busy={live !== null}>
      <p className={aiBubble}>{greeting}</p>
      {entries.map((entry) => {
        if (entry.role === "user") {
          return (
            <p className={`${bubble} self-end rounded-br-md bg-pv text-ink`} key={entry.id}>
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
                <i className="fa-solid fa-magnifying-glass mr-1.5 text-load" />
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
