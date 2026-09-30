"""Trợ lý AI: gọi LLM để chat hỏi-đáp về hệ thống điện nhà.

Bối cảnh hệ thống (số liệu thật của nhà) được server ghép sẵn và truyền vào dưới dạng
JSON; assistant chỉ lo gọi model. API key (nếu cần) nằm trong config.json (server-side) —
KHÔNG bao giờ lộ ra browser. Pluggable theo config.ai.provider; hỗ trợ:
  - 'gemini' — Google Generative Language REST API (cần api_key).
  - 'ollama' — model chạy LOCAL trên host (không cần key), REST 127.0.0.1:11434.

FUNCTION CALLING (2026-08-07): ngoài snapshot tĩnh, server truyền `tools` —
{name: {"decl": functionDeclaration (JSON Schema kiểu Gemini), "fn": async callable(args)->dict}}.
Chỉ nhánh Gemini dùng tools (vòng lặp functionCall/functionResponse, tối đa
_MAX_TOOL_ROUNDS vòng); Ollama (model local yếu) bỏ qua, chat thuần như cũ.

(Nhận định hằng ngày đã gỡ bỏ 2026-06-27 — tab Trợ lý giờ thuần chat.)
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Optional

import httpx

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# <think>...</think> của họ Qwen3/suy luận — lỡ lọt thì cắt bỏ (ta đã gửi think:false).
_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

PERSONA = (
    "Bạn là trợ lý điện mặt trời cho một GIA ĐÌNH ở TP.HCM (điện mặt trời mái nhà + pin lưu trữ), "
    "nói chuyện với chủ nhà khoảng 50 tuổi KHÔNG rành kỹ thuật. "
    "XƯNG HÔ: luôn gọi người dùng là 'bạn' — TUYỆT ĐỐI không gọi 'bác', 'anh', 'chú', 'cô', 'ông'. "
    "Trả lời bằng TIẾNG VIỆT thân thiện, NGẮN GỌN (2–4 câu), chỉ dựa trên DỮ LIỆU bên dưới; "
    "thiếu dữ liệu thì nói thẳng là chưa có, TUYỆT ĐỐI không bịa số. "
    "QUAN TRỌNG — ĐỪNG đọc lại bảng số liệu người dùng đã thấy trên màn hình, và ĐỪNG trả lời kiểu ai cũng "
    "đoán được (vd 'nên chạy máy giặt ban ngày'). Hãy đưa KẾT LUẬN/Ý CÓ ÍCH trước (nên hay không nên, vì sao, "
    "điều gì đáng chú ý mà nhìn màn hình không thấy ngay), chỉ nêu con số khi nó GIẢI THÍCH cho kết luận, và "
    "LÀM TRÒN (vd 'khoảng 38 số điện', không '38.2 kWh'). "
    "Ưu tiên quy ra TIỀN (đồng) và lời thường ngày; tránh thuật ngữ — KHÔNG dùng 'bậc 4', 'SOC', 'kWp', "
    "thay bằng 'sắp tới mức giá điện đắt hơn', 'pin còn 66%'. "
    "Khi tư vấn, dựa vào công suất dư (phát − tải), pin còn bao nhiêu, dự báo ngày mai "
    "và giá điện EVN tăng dần theo mức dùng. Viết thành câu văn liền, KHÔNG liệt kê đánh số 1/2/3, không markdown. "
    "Bạn có CÔNG CỤ tra dữ liệu (chi tiết 1 ngày bất kỳ, lịch sử theo khoảng ngày, báo cáo kỳ hoá đơn, "
    "điện nắng bị bỏ phí, dự báo thời tiết, hồ sơ 24 giờ) — khi câu hỏi nhắc tới một NGÀY/THÁNG/KỲ cụ thể "
    "hoặc cần dữ liệu không có sẵn bên dưới, hãy GỌI công cụ thay vì đoán hay nói không biết. "
    "Nếu thấy một thay đổi cài đặt RÕ RÀNG có lợi (vd mai mưa lớn nên nâng mức pin dự phòng), "
    "gọi propose_action để đề xuất — người dùng sẽ bấm xác nhận, bạn KHÔNG tự thay đổi gì."
)

# Bản English của PERSONA — CÙNG các ràng buộc hành vi (kết luận trước, làm tròn, không jargon,
# không markdown/đánh số); chỉ đổi ngôn ngữ trả lời. UI gửi lang theo toggle (i18n 2026-07-31).
PERSONA_EN = (
    "You are the solar-power assistant for a FAMILY HOME in Ho Chi Minh City, Vietnam "
    "(rooftop solar + battery storage), talking to a homeowner around 50 who is NOT technical. "
    "Reply in FRIENDLY ENGLISH, BRIEFLY (2–4 sentences), based only on the DATA below; "
    "if data is missing, say so plainly — NEVER invent numbers. "
    "IMPORTANT — do NOT read back the numbers the user already sees on screen, and do NOT give "
    "advice anyone could guess (e.g. 'run the washing machine during the day'). Lead with the "
    "CONCLUSION/USEFUL POINT (should or shouldn't, why, what's notable that the screen doesn't show), "
    "cite a number only when it EXPLAINS the conclusion, and ROUND it (say 'about 38 kWh', not '38.2 kWh'). "
    "Prefer translating things into MONEY (Vietnamese đồng) and everyday words; avoid jargon — "
    "don't say 'tier 4', 'SOC', 'kWp'; say 'close to the more expensive price level', 'battery at 66%'. "
    "When advising, use the surplus power (generation − load), the battery level, tomorrow's forecast, "
    "and the fact that EVN prices rise with monthly usage. Write flowing sentences — no numbered lists, no markdown. "
    "You have TOOLS to look up data (any single day's detail, history over a date range, billing-cycle "
    "reports, wasted solar, weather forecast, 24-hour usage profile) — when the question mentions a "
    "specific day/month/cycle or needs data not shown below, CALL a tool instead of guessing or refusing. "
    "If a settings change is CLEARLY beneficial (e.g. heavy rain tomorrow → raise the battery reserve), "
    "call propose_action to suggest it — the user confirms with a button; you never change anything yourself."
)

# Câu lùi khi model không trả lời được — theo ngôn ngữ UI.
_FALLBACK = {
    "vi": {"blocked": "Xin lỗi, mình chưa trả lời được câu này.",
           "empty": "Xin lỗi, mình chưa có câu trả lời.",
           "ask": "Bạn muốn hỏi gì về hệ thống điện mặt trời?"},
    "en": {"blocked": "Sorry, I can't answer that one.",
           "empty": "Sorry, I don't have an answer yet.",
           "ask": "What would you like to know about your solar system?"},
}

class Assistant:
    def __init__(self, cfg: Optional[dict]):
        cfg = cfg or {}
        self.provider = (cfg.get("provider") or "gemini").lower()
        self.model = cfg.get("model") or "gemini-flash-lite-latest"
        # Model dự phòng khi model chính trả 429/5xx dai dẳng (gemini-3.5-flash free tier
        # hay 503 giờ cao điểm). Trống -> không fallback.
        self.fallback_model = cfg.get("fallback_model") or ""
        self.api_key = cfg.get("api_key") or ""
        self.max_tokens = int(cfg.get("max_tokens", 800))
        # base_url cho Ollama (local) khi chat chạy bằng model local.
        self.ollama_base = (cfg.get("base_url") or "http://127.0.0.1:11434").rstrip("/")

    SUPPORTED = ("gemini", "ollama")

    def _ok(self, provider: str, api_key: str, model: str) -> bool:
        # ollama chạy local -> không cần key; gemini cần key. Cả hai cần model.
        if provider not in self.SUPPORTED or not model:
            return False
        return True if provider == "ollama" else bool(api_key)

    @property
    def chat_enabled(self) -> bool:
        return self._ok(self.provider, self.api_key, self.model)

    # ---- ghép system text (persona + dữ liệu JSON) ----
    def _system_text(self, context: dict, persona: str = PERSONA, label: str = "") -> str:
        ctx = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        head = label or "DỮ LIỆU HỆ THỐNG (JSON, số liệu thật):"
        return persona + "\n\n" + head + "\n" + ctx

    # Vòng lặp tool tối đa: mỗi vòng model có thể gọi vài hàm; quá số này -> ép trả lời
    # bằng text (bỏ tools khỏi body) để không xoay vô hạn / đốt quota.
    _MAX_TOOL_ROUNDS = 5

    # ---- backends ----
    async def _gemini(self, model: str, api_key: str, system_text: str,
                      msgs: list, max_tokens: int, temperature: float, lang: str = "vi",
                      tools: Optional[dict] = None) -> str:
        url = GEMINI_URL.format(model=model)
        contents = [{"role": "user" if m["role"] == "user" else "model",
                     "parts": [{"text": m["content"]}]} for m in msgs]
        body = {
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if tools:
            body["tools"] = [{"functionDeclarations": [t["decl"] for t in tools.values()]}]
        async with httpx.AsyncClient(timeout=90) as client:
            for round_i in range(self._MAX_TOOL_ROUNDS + 1):
                if round_i == self._MAX_TOOL_ROUNDS:
                    body.pop("tools", None)  # vòng chót: ép trả lời text, không cho gọi thêm
                # Key gửi qua HEADER (không phải query param) -> KHÔNG dính vào URL trong thông báo lỗi
                # của httpx, tránh lộ key ra client/log khi Gemini trả 4xx/5xx.
                # Retry nhẹ cho lỗi TẠM (429 rate-limit / 5xx quá tải — gemini-3.5-flash hay dính
                # 503 giờ cao điểm): thử lại tối đa 2 lần, backoff ngắn; lỗi khác raise luôn.
                for attempt in range(3):
                    r = await client.post(url, headers={"x-goog-api-key": api_key}, json=body)
                    if r.status_code in (429, 500, 502, 503) and attempt < 2:
                        await asyncio.sleep(1.5 * (attempt + 1))
                        continue
                    break
                r.raise_for_status()
                data = r.json()
                cands = data.get("candidates") or []
                if not cands:
                    # có thể bị bộ lọc an toàn chặn -> trả thông báo nhẹ nhàng thay vì lỗi
                    return _FALLBACK[lang]["blocked"]
                parts = ((cands[0].get("content") or {}).get("parts")) or []
                calls = [p["functionCall"] for p in parts if isinstance(p, dict) and p.get("functionCall")]
                if not calls or not tools:
                    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
                    return text or _FALLBACK[lang]["empty"]
                # Model muốn tra dữ liệu: chạy từng hàm, nối lượt model + functionResponse rồi hỏi tiếp.
                contents.append({"role": "model", "parts": parts})
                contents.append({"role": "user", "parts": await self._exec_tools(tools, calls)})
        return _FALLBACK[lang]["empty"]

    @staticmethod
    async def _exec_tools(tools: dict, calls: list) -> list:
        """Chạy các functionCall -> list functionResponse parts. Lỗi tool KHÔNG raise —
        trả {'error'} cho model tự nói "chưa lấy được dữ liệu"."""
        fr_parts = []
        for fc in calls:
            name = fc.get("name") or ""
            args = fc.get("args") or {}
            ent = tools.get(name)
            if ent is None:
                result = {"error": f"unknown tool: {name}"}
            else:
                try:
                    result = await ent["fn"](args)
                except Exception as e:
                    result = {"error": f"{type(e).__name__}: {e}"}
            if not isinstance(result, dict):  # Gemini bắt buộc response là object
                result = {"result": result}
            fr_parts.append({"functionResponse": {"name": name, "response": result}})
        return fr_parts

    async def _gemini_stream(self, model: str, api_key: str, system_text: str,
                             msgs: list, max_tokens: int, temperature: float,
                             lang: str = "vi", tools: Optional[dict] = None):
        """Bản STREAM của _gemini (streamGenerateContent?alt=sse) — async generator phát:
          {'type':'status','tool':name}  — model đang gọi công cụ tra dữ liệu
          {'type':'delta','text':chunk}  — mảnh text trả lời (phát dần)
        Vòng tool vẫn như bản thường: round có functionCall -> chạy tool -> round mới;
        text chỉ chảy ra ở round trả lời. Kết thúc generator = xong (server tự phát 'done')."""
        url = GEMINI_URL.format(model=model).replace(
            ":generateContent", ":streamGenerateContent") + "?alt=sse"
        contents = [{"role": "user" if m["role"] == "user" else "model",
                     "parts": [{"text": m["content"]}]} for m in msgs]
        body = {
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if tools:
            body["tools"] = [{"functionDeclarations": [t["decl"] for t in tools.values()]}]
        emitted_any = False
        async with httpx.AsyncClient(timeout=90) as client:
            for round_i in range(self._MAX_TOOL_ROUNDS + 1):
                if round_i == self._MAX_TOOL_ROUNDS:
                    body.pop("tools", None)  # vòng chót: ép trả lời text
                # Retry MỞ stream cho lỗi tạm (429/5xx) — chỉ trước khi có dữ liệu.
                for attempt in range(3):
                    async with client.stream("POST", url, headers={"x-goog-api-key": api_key},
                                             json=body) as r:
                        if r.status_code in (429, 500, 502, 503) and attempt < 2:
                            await r.aread()
                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue
                        if r.status_code >= 400:
                            await r.aread()  # nạp body để raise có nội dung, không treo stream
                            r.raise_for_status()
                        # Gom parts của CẢ round (để nối contents nếu có functionCall);
                        # text part phát delta NGAY khi tới.
                        round_parts: list = []
                        calls: list = []
                        async for line in r.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            try:
                                chunk = json.loads(line[6:])
                            except Exception:
                                continue
                            cands = chunk.get("candidates") or []
                            parts = ((cands[0].get("content") or {}).get("parts")) if cands else None
                            for p in parts or []:
                                if not isinstance(p, dict):
                                    continue
                                if p.get("functionCall"):
                                    calls.append(p["functionCall"])
                                    round_parts.append(p)
                                elif p.get("text"):
                                    round_parts.append(p)
                                    emitted_any = True
                                    yield {"type": "delta", "text": p["text"]}
                    break  # stream đọc xong (hoặc raise) -> thoát vòng retry
                if not calls or not tools:
                    if not emitted_any:
                        # round cuối không text (bị chặn/parts rỗng) -> câu lùi như bản thường
                        yield {"type": "delta", "text": _FALLBACK[lang]["blocked"]}
                    return
                for fc in calls:  # báo UI "đang tra dữ liệu" theo từng công cụ
                    yield {"type": "status", "tool": fc.get("name") or ""}
                contents.append({"role": "model", "parts": round_parts})
                contents.append({"role": "user", "parts": await self._exec_tools(tools, calls)})
        if not emitted_any:
            yield {"type": "delta", "text": _FALLBACK[lang]["empty"]}

    async def _ollama(self, model: str, system_text: str,
                      msgs: list, max_tokens: int, temperature: float, lang: str = "vi") -> str:
        url = self.ollama_base + "/api/chat"
        messages = [{"role": "system", "content": system_text}]
        messages += [{"role": m["role"], "content": m["content"]} for m in msgs]
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,  # tắt suy luận họ Qwen3 (không thì lòi đoạn <think> + chậm)
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        # CPU local (host N100) chậm: nhận định ~12–45s kể cả lúc nạp model lần đầu -> timeout rộng.
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(url, json=body)
            r.raise_for_status()
            data = r.json()
        text = ((data.get("message") or {}).get("content") or "").strip()
        text = _THINK_RE.sub("", text).strip()  # cắt <think> lỡ lọt
        return text or _FALLBACK[lang]["empty"]

    async def _call(self, provider: str, model: str, api_key: str, system_text: str,
                    msgs: list, max_tokens: int, temperature: float, lang: str = "vi",
                    tools: Optional[dict] = None) -> str:
        if provider == "gemini":
            return await self._gemini(model, api_key, system_text, msgs, max_tokens,
                                      temperature, lang, tools=tools)
        if provider == "ollama":
            # model local yếu + lib không chắc theo được vòng tool -> chat thuần, bỏ tools
            return await self._ollama(model, system_text, msgs, max_tokens, temperature, lang)
        raise ValueError("provider AI chưa hỗ trợ: " + provider)

    async def chat(self, context: dict, messages: list, lang: str = "vi",
                   tools: Optional[dict] = None) -> str:
        """messages: [{role:'user'|'assistant', content:str}] (đa lượt). Trả lời text.
        lang: 'vi'|'en' theo toggle ngôn ngữ UI — chọn persona + câu lùi tương ứng.
        tools: {name: {'decl','fn'}} — hàm tra dữ liệu server-side (chỉ Gemini dùng)."""
        lang = "en" if lang == "en" else "vi"
        msgs = self._norm_msgs(messages)
        if not msgs:
            return _FALLBACK[lang]["ask"]
        system_text = self._system_for(context, lang)
        try:
            return await self._call(self.provider, self.model, self.api_key, system_text,
                                    msgs, self.max_tokens, 0.4, lang, tools=tools)
        except httpx.HTTPStatusError as e:
            # Model chính quá tải/hết quota (đã retry trong _gemini) -> thử model dự phòng
            # 1 lần cho trọn cuộc chat; lỗi khác (4xx cấu hình) thì để nổ như cũ.
            fb = self.fallback_model
            if fb and fb != self.model and e.response.status_code in (429, 500, 502, 503):
                return await self._call(self.provider, fb, self.api_key, system_text,
                                        msgs, self.max_tokens, 0.4, lang, tools=tools)
            raise

    @staticmethod
    def _norm_msgs(messages: list) -> list:
        """Chuẩn hoá lượt chat: 12 lượt cuối, cắt 2000 ký tự, lượt đầu phải là 'user'
        (Gemini bắt buộc — bỏ các lượt 'assistant' dẫn đầu như lời chào UI)."""
        msgs = []
        for m in messages[-12:]:  # giới hạn ngữ cảnh để gọn + rẻ
            role = "user" if m.get("role") == "user" else "assistant"
            text = str(m.get("content") or "")[:2000]
            if text:
                msgs.append({"role": role, "content": text})
        while msgs and msgs[0]["role"] != "user":
            msgs.pop(0)
        return msgs

    def _system_for(self, context: dict, lang: str) -> str:
        persona = PERSONA_EN if lang == "en" else PERSONA
        # nhãn khối dữ liệu theo cùng ngôn ngữ với persona (trước đây luôn VI kể cả chat EN)
        label = "SYSTEM DATA (JSON, real readings):" if lang == "en" else ""
        return self._system_text(context, persona=persona, label=label)

    async def chat_stream(self, context: dict, messages: list, lang: str = "vi",
                          tools: Optional[dict] = None):
        """Bản STREAM của chat() — async generator phát event dict (xem _gemini_stream).
        Chỉ Gemini stream thật; provider khác (Ollama) chạy chat() thường rồi phát 1 delta
        duy nhất — frontend không cần phân biệt. Fallback model như chat(): chỉ khi lỗi
        TẠM và CHƯA phát ra chữ nào (đã phát rồi mà đổi model thì câu trả lời chắp vá)."""
        lang = "en" if lang == "en" else "vi"
        msgs = self._norm_msgs(messages)
        if not msgs:
            yield {"type": "delta", "text": _FALLBACK[lang]["ask"]}
            return
        if self.provider != "gemini":
            yield {"type": "delta",
                   "text": await self._call(self.provider, self.model, self.api_key,
                                            self._system_for(context, lang), msgs,
                                            self.max_tokens, 0.4, lang)}
            return
        system_text = self._system_for(context, lang)
        emitted = False
        try:
            async for ev in self._gemini_stream(self.model, self.api_key, system_text,
                                                msgs, self.max_tokens, 0.4, lang, tools=tools):
                emitted = emitted or ev.get("type") == "delta"
                yield ev
        except httpx.HTTPStatusError as e:
            fb = self.fallback_model
            if emitted or not fb or fb == self.model \
                    or e.response.status_code not in (429, 500, 502, 503):
                raise
            async for ev in self._gemini_stream(fb, self.api_key, system_text,
                                                msgs, self.max_tokens, 0.4, lang, tools=tools):
                yield ev
