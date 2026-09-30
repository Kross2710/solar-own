// Shapes of /api/ai_status, /api/chat (SSE), /api/action and /api/notices.

export interface AiStatusResponse {
  enabled: boolean;
}

export type ChatRole = "user" | "assistant";

export interface ProposedAction {
  kind: "set_reserve" | string;
  params: { reserve_pct?: number };
  current: number;
  reason: string;
}

export type ActionState = "pending" | "applying" | "applied" | "dismissed" | "failed";

export type ChatEntry =
  | { id: string; type: "message"; role: ChatRole; content: string; error?: boolean }
  | { id: string; type: "action"; action: ProposedAction; state: ActionState };

export type ChatStreamEvent =
  | { type: "status"; tool: string }
  | { type: "delta"; text: string }
  | { type: "error"; error_code: string }
  | { type: "done"; actions: ProposedAction[] };

export type NoticeSeverity = "warn" | "info";

interface NoticeBase {
  id: number;
  ts: string;                 // "YYYY-MM-DDTHH:MM", Vietnam time
  dkey: string;
  severity: NoticeSeverity;
  expires: string;
}

export type Notice = NoticeBase &
  (
    | { kind: "offline"; data: { since: string } }
    | { kind: "night_load_high"; data: { night: string; night_kwh: number; avg_kwh: number } }
    | { kind: "bill_high"; data: { proj: number; last: number; last_cycle: string; pct: number } }
    | {
        kind: "tier_ahead";
        data: { tier: number; price: number; cur_price: number; to_next_kwh: number; days_left: number | null };
      }
    | { kind: "wasted_sun_up"; data: { lost_kwh: number; prev_kwh: number; value: number; full_at: string | null } }
  );

export interface NoticesResponse {
  notices: Notice[];
}
