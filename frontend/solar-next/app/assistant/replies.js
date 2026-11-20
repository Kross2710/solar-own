import {errorText,parseSse,toApiMessages,toolLabel} from "./messages";

export const examples = [
  ["When should I run appliances?", "In the sample hourly profile, 08:00–17:00 usually has enough solar for the house. At noon the sample system produces 3.5 kW against 1.2 kW of load."],
  ["Will the battery last tonight?", "The sample battery is at 96%. With a 20% reserve, about 10.6 kWh is available, compared with 8 kWh on a typical night."],
];
export function demoReply(text,t) {
  if (text.includes("Last night") || text.includes("Đêm qua")) return "The sample night used 12 kWh, about 4 kWh above average. Check the overnight load profile for sustained loads such as air conditioning.";
  return examples.find(([q])=>text===t(q))?.[1] ?? "This preview has sample replies for the suggested questions. Open the live assistant to ask about your system.";
}
export async function streamReply(history, update, lang, signal) {
  const response = await fetch("/api/chat", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body:JSON.stringify({messages:toApiMessages(history),lang}), signal,
  });
  if (!response.ok || !response.body || !response.headers.get("content-type")?.includes("text/event-stream")) {
    const body = await response.json().catch(()=>null);
    throw new Error(body?.enabled===false ? "Chat is disabled." : errorText(body?.error_code || "network"));
  }
  const reader=response.body.getReader(), decoder=new TextDecoder();
  let reply="", buffer="", status="";
  try {
    while (true) {
      const chunk=await reader.read();
      const decoded = chunk.done ? decoder.decode() : decoder.decode(chunk.value,{stream:true});
      const tail = chunk.done ? "\n\n" : "";
      const parsed=parseSse((buffer+decoded+tail).replaceAll("\r\n","\n"));
      buffer=parsed.rest;
      for(const event of parsed.events) {
        if(event.type==="delta"){reply+=event.text;status="";}
        if(event.type==="status") status=toolLabel(event.tool);
        if(event.type==="error") throw new Error(errorText(event.error_code));
        if(event.type==="done") {
          if (reply) return reply;
          throw new Error(errorText());
        }
        update(reply,status);
      }
      if (chunk.done) break;
    }
    throw new Error("The reply did not finish. Please try again.");
  } finally {await reader.cancel().catch(()=>{});}
}
