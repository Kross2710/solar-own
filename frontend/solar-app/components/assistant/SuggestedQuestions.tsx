import { SUGGESTED_QUESTIONS } from "@/app/assistant/assistant.helpers";

interface SuggestedQuestionsProps {
  variant: "cards" | "chips";
  disabled?: boolean;
  onAsk: (question: string) => void;
}

export default function SuggestedQuestions({ variant, disabled, onAsk }: SuggestedQuestionsProps) {
  if (variant === "chips") {
    return (
      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none]" role="group" aria-label="Suggested questions">
        {SUGGESTED_QUESTIONS.map((item) => (
          <button
            className="shrink-0 rounded-full border border-white/10 bg-[#0a0e18]/90 px-3 py-1.5 text-[12px] text-zinc-200 backdrop-blur-xl transition-colors hover:border-[#ffc76b]/40 disabled:opacity-40"
            disabled={disabled}
            key={item.q}
            onClick={() => onAsk(item.q)}
            type="button"
          >
            <i className={`fa-solid ${item.icon} mr-1.5`} style={{ color: item.color }} />
            {item.q}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-2" role="group" aria-label="Suggested questions">
      {SUGGESTED_QUESTIONS.map((item) => (
        <button
          className="flex flex-col items-start gap-2 rounded-[18px] border border-white/10 bg-[#0a0e18]/90 p-3 text-left backdrop-blur-xl transition hover:border-[#ffc76b]/45 active:scale-[0.97] disabled:opacity-40"
          disabled={disabled}
          key={item.q}
          onClick={() => onAsk(item.q)}
          type="button"
        >
          <i className={`fa-solid ${item.icon} text-[18px]`} style={{ color: item.color }} />
          <span className="text-[12.5px] leading-snug text-zinc-100">{item.q}</span>
        </button>
      ))}
    </div>
  );
}
