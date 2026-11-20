import { fmtMoney, fmtNum, parseDateMonth } from "../shared/format";
const TOOL_LABELS = {
    get_day_detail: "Checking that day's hour-by-hour data…",
    get_daily_history: "Going through your daily history…",
    get_cycle_report: "Opening the billing cycle report…",
    get_curtailment: "Checking wasted sunshine…",
    get_weather_forecast: "Checking the weather forecast…",
    get_hourly_profile: "Looking at your usual day, hour by hour…",
};
export function toolLabel(tool) {
    return TOOL_LABELS[tool] ?? "Looking up your data…";
}
export function errorText(code) {
    if (code === "rate_limit")
        return "You're asking a bit fast — try again in a moment.";
    if (code === "network")
        return "Network error — try again later.";
    if (code)
        return "The assistant hit an error — try again later.";
    return "No reply yet — please try again.";
}
export function noticeView(notice, lang) {
    if (lang === "vi") {
        const d = notice.data;
        switch (notice.kind) {
            case "offline":
                return {title:"Hệ thống ngừng gửi số liệu", detail:"Lần đo cuối lúc "+d.since.slice(11)+".", ask:"Hệ thống ngừng gửi dữ liệu từ "+d.since.slice(11)+". Tôi nên kiểm tra gì?"};
            case "night_load_high":
                return {title:"Đêm qua dùng "+fmtNum(d.night_kwh,lang)+" kWh",detail:"Mức trung bình là "+fmtNum(d.avg_kwh,lang)+" kWh.",ask:"Đêm qua dùng "+fmtNum(d.night_kwh,lang)+" kWh, cao hơn mức trung bình "+fmtNum(d.avg_kwh,lang)+" kWh. Nguyên nhân có thể là gì?"};
            case "bill_high":
                return {title:"Hóa đơn dự kiến "+fmtMoney(d.proj),detail:"Cao hơn "+d.pct+"% so với hóa đơn trước ("+fmtMoney(d.last)+").",ask:"Vì sao hóa đơn dự kiến tăng "+d.pct+"% và tôi nên điều chỉnh gì?"};
            case "tier_ahead":
                return {title:"Sắp tới bậc giá "+d.tier,detail:"Còn "+fmtNum(d.to_next_kwh,lang)+" kWh trước khi giá tăng lên "+fmtMoney(d.price)+"/kWh.",ask:"Còn "+fmtNum(d.to_next_kwh,lang)+" kWh trước bậc giá tiếp theo. Làm sao hạn chế mua điện?"};
            case "wasted_sun_up":
                return {title:"Khoảng "+fmtNum(d.lost_kwh,lang)+" kWh chưa tận dụng",detail:"Tuần trước ước tính "+fmtNum(d.prev_kwh,lang)+" kWh.",ask:"Tuần này còn khoảng "+fmtNum(d.lost_kwh,lang)+" kWh điện mặt trời chưa tận dụng. Tôi nên dời tải lúc nào?"};
        }
    }
    switch (notice.kind) {
        case "offline":
            return {
                icon: "fa-plug-circle-xmark",
                title: "The solar system isn't reporting",
                detail: `No data since ${notice.data.since.slice(11)}. Check the inverter's Wi-Fi or power.`,
                ask: `The solar system stopped reporting at ${notice.data.since.slice(11)}. What should I check?`,
            };
        case "night_load_high":
            return {
                icon: "fa-moon",
                title: `Last night used ~${fmtNum(notice.data.night_kwh)} kWh`,
                detail: `Well above the usual ${fmtNum(notice.data.avg_kwh)} kWh. Was something left running?`,
                ask: `Last night (${parseDateMonth(notice.data.night)}) the house used about ${fmtNum(notice.data.night_kwh)} kWh vs the usual ${fmtNum(notice.data.avg_kwh)} kWh. What could explain it?`,
            };
        case "bill_high":
            return {
                icon: "fa-receipt",
                title: `Bill heading to ~${fmtMoney(notice.data.proj)}`,
                detail: `${notice.data.pct}% more than the last real EVN bill (${fmtMoney(notice.data.last)}).`,
                ask: `This cycle's bill is heading to about ${fmtMoney(notice.data.proj)}, ${notice.data.pct}% more than the last EVN bill. Why, and what can I do?`,
            };
        case "tier_ahead": {
            const when = notice.data.days_left != null ? `in about ${notice.data.days_left} days` : "before the cycle ends";
            return {
                icon: "fa-arrow-trend-up",
                title: `Tier ${notice.data.tier} price ${when}`,
                detail: `At this pace, grid power goes from ${fmtMoney(notice.data.cur_price)} to ${fmtMoney(notice.data.price)}/kWh after ${fmtNum(notice.data.to_next_kwh)} more kWh.`,
                ask: `I'm about ${fmtNum(notice.data.to_next_kwh)} kWh away from the ${fmtMoney(notice.data.price)}/kWh price. How can I stay below it this cycle?`,
            };
        }
        case "wasted_sun_up":
            return {
                icon: "fa-sun",
                title: `~${fmtNum(notice.data.lost_kwh)} kWh of sun wasted this week`,
                detail: `Up from ~${fmtNum(notice.data.prev_kwh)} kWh the week before — estimated curtailed energy${notice.data.full_at ? `. Battery usually full by ${notice.data.full_at}` : ""}.`,
                ask: `This week about ${fmtNum(notice.data.lost_kwh)} kWh of sunshine went unused, up from ${fmtNum(notice.data.prev_kwh)} kWh. How can I use more of it?`,
            };
    }
}
// ---------- chat stream ----------
// Split a raw SSE buffer into complete events; the incomplete tail is returned for the next read.
export function parseSse(buffer) {
    const blocks = buffer.split("\n\n");
    const rest = blocks.pop() ?? "";
    const events = [];
    for (const block of blocks) {
        const line = block.split("\n").find((l) => l.startsWith("data: "));
        if (!line)
            continue;
        try {
            events.push(JSON.parse(line.slice(6)));
        }
        catch {
            // A malformed event is skipped rather than breaking the whole reply.
        }
    }
    return { events, rest };
}
export function toApiMessages(entries) {
    // Match the provider's context window before sending the request.
    const recent = entries.filter(e => e.type === "message" && !e.error && !e.stopped && e.content)
        .slice(-12).map(e => ({role:e.role, content:Array.from(e.content).slice(0,2000).join("")}));
    const start = recent.findIndex(e => e.role === "user");
    return start < 0 ? [] : recent.slice(start);
}
let idCounter = 0;
export function entryId() {
    idCounter += 1;
    return `${Date.now().toString(36)}-${idCounter}`;
}
