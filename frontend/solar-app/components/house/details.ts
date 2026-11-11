import { siteTime } from "@/lib/time";
import { sunTimes } from "@/lib/sun";
import { FLOW_MIN_W, fmtPower, SceneData } from "./flow";

export type DetailKey = "solar" | "home" | "battery" | "grid";

export interface Detail {
  icon: string;
  tone: string;
  title: string;
  lines: string[];
}

function clock(date: Date): string {
  return siteTime(date);
}

// Around sunrise and sunset the usual output is too small for a percentage to mean much.
const COMPARE_FROM_W = 500;

// Before sunrise the coming sun is today's; after sunset it is tomorrow's.
function nightDetail(scene: SceneData): Detail {
  const today = sunTimes(scene.now, scene.lat, scene.lon);
  const lines: string[] = [];
  let rise: Date | null;
  if (today && scene.now < today.rise) {
    rise = today.rise;
    if (scene.expectedKwh) lines.push(`~${Math.round(scene.expectedKwh)} kWh expected today`);
  } else {
    const tomorrow = new Date(scene.now.getTime() + 86_400_000);
    rise = sunTimes(tomorrow, scene.lat, scene.lon)?.rise ?? null;
    if (scene.todayKwh != null) lines.push(`Made ${scene.todayKwh.toFixed(1)} kWh today`);
    if (scene.tomorrowKwh) lines.push(`~${Math.round(scene.tomorrowKwh)} kWh expected tomorrow`);
  }
  return { icon: "fa-moon", tone: "text-batt", title: rise ? `Night · sunrise ${clock(rise)}` : "Night", lines };
}

function solarDetail(scene: SceneData, day: boolean): Detail {
  const { todayKwh, expectedKwh, typicalPvW } = scene;
  if (!day) return nightDetail(scene);

  const lines: string[] = [];
  if (todayKwh != null) {
    lines.push(expectedKwh ? `${todayKwh.toFixed(1)} of ~${Math.round(expectedKwh)} kWh expected today` : `${todayKwh.toFixed(1)} kWh today`);
  }
  if (typicalPvW && typicalPvW >= COMPARE_FROM_W) {
    const pct = Math.round((scene.pvW / typicalPvW) * 100);
    lines.push(`${pct}% of the usual ~${fmtPower(typicalPvW)} at this hour`);
  }
  return { icon: "fa-sun", tone: "text-pv", title: `Solar · ${fmtPower(scene.pvW)}`, lines };
}

function homeDetail(scene: SceneData): Detail {
  const { consKwh, buyKwh } = scene;
  const lines: string[] = [];
  if (consKwh != null) lines.push(`Used ${consKwh.toFixed(1)} kWh today`);
  if (consKwh && buyKwh != null) {
    const self = Math.max(0, Math.min(100, Math.round((1 - buyKwh / consKwh) * 100)));
    lines.push(`${self}% self-powered today`);
  }
  return { icon: "fa-house", tone: "text-load", title: `Home · ${fmtPower(scene.loadW)}`, lines };
}

function batteryDetail(scene: SceneData): Detail {
  const { battW } = scene;
  const action = battW >= FLOW_MIN_W ? `charging ${fmtPower(battW)}` : battW <= -FLOW_MIN_W ? `powering ${fmtPower(battW)}` : "idle";
  const lines = scene.battery ? [scene.battery.title, scene.battery.detail] : [];
  return { icon: "fa-battery-half", tone: "text-batt", title: `Battery ${Math.round(scene.soc)}% · ${action}`, lines };
}

function gridDetail(scene: SceneData): Detail {
  const { gridW, buyKwh, tier } = scene;
  const title =
    gridW > FLOW_MIN_W ? `Buying ${fmtPower(gridW)} from EVN` : gridW < -FLOW_MIN_W ? `Sending ${fmtPower(gridW)} to the grid` : "Grid idle";
  const lines: string[] = [];
  if (buyKwh != null) lines.push(`Bought ${buyKwh.toFixed(1)} kWh today`);
  if (tier) lines.push(tier.price != null ? `Tier ${tier.number} · ${tier.price.toLocaleString("vi-VN")} đ/kWh` : `Tier ${tier.number}`);
  return { icon: "fa-bolt", tone: gridW > FLOW_MIN_W ? "text-grid-in" : "text-good", title, lines };
}

export function sceneDetail(key: DetailKey, scene: SceneData, day: boolean): Detail {
  if (key === "solar") return solarDetail(scene, day);
  if (key === "home") return homeDetail(scene);
  if (key === "battery") return batteryDetail(scene);
  return gridDetail(scene);
}
