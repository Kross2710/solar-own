"use client";

import { CSSProperties, useState } from "react";
import { COLORS } from "@/lib/colors";
import { skyPosition } from "@/lib/sun";
import { DetailKey, sceneDetail } from "./details";
import {
  Flow,
  FLOW_MIN_W,
  fmtPower,
  SceneData,
  usePageVisible,
  useReducedMotion,
  useRisingEdge,
  useSvgPause,
  useTween,
} from "./flow";
import { SkyBackdrop } from "./Sky";

// Wires all meet at the inverter on the right wall. Solar leaves the panel's lower edge,
// crosses the eave at a junction box and runs down the wall.
const PATH_PV = "M190.5,159.6 L195.75,166.2 L195.75,201";
const PATH_BATT = "M196,212 L196,228 Q196,234 190.6,236.7 L185.4,239.3 Q180,242 174.6,239.4 L137,221";
const PATH_LOAD = "M196,212 L196,228 Q196,234 201.4,231.3 L235.8,214.5 Q243,211 243,203 L243,192";
const PATH_GRID = "M196,212 L196,250 Q196,258 204,258 L318,258";

// Sun and moon travel this half-ellipse, rising and setting behind the house.
const ARC = { cx: 180, cy: 150, rx: 150, ry: 108 };
// Panels in strong sun read as sky reflected in glass, not as yellow.
const PANEL_SHEEN = "#7f9fdc";
const STARS: [number, number, number][] = [
  [40, 40, 3.2], [95, 22, 4.1], [150, 46, 3.6], [262, 28, 4.6], [318, 60, 3.9], [66, 92, 5.2], [306, 104, 4.4],
];

const PANEL_CELLS = [0.15, 0.41, 0.67].flatMap((y) => [0.09, 0.303, 0.516, 0.729].map((x) => [x, y]));

// One wavelength of the battery surface is 0.06 wide, in the battery's local units.
const WAVE = (() => {
  let d = "M0.2,0 q0.015,0.022 0.03,0";
  for (let i = 1; i < 20; i++) d += " t0.03,0";
  return `${d} L0.8,-1 L0.2,-1 Z`;
})();

const HOME_BRIGHT_W = 3500;
const SUN_UP_W = 100;
const FULL_SOC = 99.5;
// EVN tiers from here on cost noticeably more than the first ones.
const HIGH_TIER = 4;

// Battery top center in scene units, for effects drawn outside its skewed group.
const BATT_TOP = { x: 137, y: 178 };
const SPARKLES = [
  [-15, -4],
  [13, -12],
  [-5, -20],
  [17, 5],
  [-18, 12],
];
const SPARKLE_PATH = "M0,-7 L1.6,-1.6 L7,0 L1.6,1.6 L0,7 L-1.6,1.6 L-7,0 L-1.6,-1.6 Z";

const VIEW = { w: 360, h: 300 };

// One-shot css animation on an svg element that scales around its own center.
function once(name: string, ms: number, delayMs = 0): CSSProperties {
  return {
    transformBox: "fill-box",
    transformOrigin: "center",
    animation: `${name} ${ms}ms ease-out ${delayMs}ms both`,
  };
}

function spot(cx: number, cy: number, w: number, h: number): CSSProperties {
  return {
    left: `${((cx - w / 2) / VIEW.w) * 100}%`,
    top: `${((cy - h / 2) / VIEW.h) * 100}%`,
    width: `${(w / VIEW.w) * 100}%`,
    height: `${(h / VIEW.h) * 100}%`,
  };
}

function socColor(soc: number): string {
  return soc <= 20 ? COLORS.gridIn : soc <= 50 ? COLORS.pv : COLORS.good;
}

export default function LivingHouse({ scene }: { scene: SceneData }) {
  const reduced = useReducedMotion();
  const visible = usePageVisible();
  const svgRef = useSvgPause(visible);
  const paused = !visible;

  const { pvW, loadW, battW, gridW, soc, capacityKw } = scene;
  const sky = skyPosition(scene.now, scene.lat, scene.lon);
  const angle = Math.PI * sky.progress;
  const bodyX = ARC.cx - ARC.rx * Math.cos(angle);
  const bodyY = ARC.cy - ARC.ry * Math.sin(angle);

  const pvRatio = Math.min(1, pvW / (capacityKw * 1000 * 0.75));
  const loadRatio = Math.min(1, loadW / HOME_BRIGHT_W);
  const level = 0.06 + 0.58 * Math.max(0, Math.min(1, soc / 100));
  const charging = battW >= FLOW_MIN_W;
  const anyFlow = [pvW, loadW, battW, gridW].some((w) => Math.abs(w) >= FLOW_MIN_W);

  const pvShown = useTween(pvW);
  const loadShown = useTween(loadW);
  const battShown = useTween(battW);
  const gridShown = useTween(gridW);

  // The house shadow falls away from the sun and stretches when it is low.
  const sunOffset = sky.day ? bodyX - ARC.cx : 0;

  const wakeCount = useRisingEdge(sky.day && pvW >= SUN_UP_W);
  const fullCount = useRisingEdge(soc >= FULL_SOC);
  const highTier = gridW > FLOW_MIN_W && (scene.tier?.number ?? 0) >= HIGH_TIER;
  const selfPowered = (scene.consKwh ?? 0) >= 2 && scene.buyKwh != null && scene.buyKwh < 0.05;

  const [open, setOpen] = useState<DetailKey | null>(null);
  const detail = open ? sceneDetail(open, scene, sky.day) : null;
  const toggle = (key: DetailKey) => setOpen((current) => (current === key ? null : key));

  return (
    <div
      className="relative mx-auto w-full max-w-[420px] select-none lg:max-w-[540px]"
      onKeyDown={(event) => event.key === "Escape" && setOpen(null)}
    >
      <div className="relative" onClick={() => setOpen(null)}>
        <svg ref={svgRef} className="block h-auto w-full" viewBox="0 0 360 300" aria-hidden="true">
          <SkyBackdrop day={sky.day} progress={sky.progress} sunX={bodyX} />
          <defs>
            <radialGradient id="lhShadow">
              <stop offset="0%" stopColor="rgba(0,0,0,.55)" />
              <stop offset="100%" stopColor="rgba(0,0,0,0)" />
            </radialGradient>
            <radialGradient id="lhSunGlow">
              <stop offset="0%" stopColor={COLORS.pv} stopOpacity=".55" />
              <stop offset="100%" stopColor={COLORS.pv} stopOpacity="0" />
            </radialGradient>
            <radialGradient id="lhFullGlow">
            <stop offset="0%" stopColor={COLORS.good} stopOpacity=".45" />
            <stop offset="100%" stopColor={COLORS.good} stopOpacity="0" />
          </radialGradient>
          <radialGradient id="lhTierGlow">
              <stop offset="0%" stopColor={COLORS.gridIn} stopOpacity=".6" />
              <stop offset="100%" stopColor={COLORS.gridIn} stopOpacity="0" />
            </radialGradient>
            <radialGradient id="lhMoonGlow">
              <stop offset="0%" stopColor="#9fb4ff" stopOpacity=".22" />
              <stop offset="100%" stopColor="#9fb4ff" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="lhGlint" x1="0" x2="1" y1="0" y2="0">
              <stop offset="0" stopColor="#fff" stopOpacity="0" />
              <stop offset=".5" stopColor="#fff" stopOpacity=".55" />
              <stop offset="1" stopColor="#fff" stopOpacity="0" />
            </linearGradient>
            <clipPath id="lhPanelClip">
              <rect x="0.06" y="0.1" width="0.88" height="0.82" />
            </clipPath>
            <clipPath id="lhBattClip">
              <rect x="0.32" y="0.06" width="0.18" height="0.58" />
            </clipPath>
            <mask id="lhMoonMask">
              <circle cx={bodyX} cy={bodyY} r="8" fill="#fff" />
              <circle cx={bodyX + 4} cy={bodyY - 3} r="7" fill="#000" />
            </mask>
          </defs>

          {/* Sky */}
          <path
            d={`M${ARC.cx - ARC.rx},${ARC.cy} A${ARC.rx},${ARC.ry} 0 0 1 ${ARC.cx + ARC.rx},${ARC.cy}`}
            fill="none"
            stroke="rgba(255,255,255,0.07)"
            strokeWidth="1"
            strokeDasharray="1 5"
          />
          {sky.day ? (
            <g>
              <circle cx={bodyX} cy={bodyY} r="42" fill="url(#lhSunGlow)" style={{ opacity: 0.25 + 0.5 * pvRatio, transition: "opacity 1s" }} />
              <circle
                cx={bodyX}
                cy={bodyY}
                r="8"
                fill={COLORS.pv}
                style={{ opacity: 0.55 + 0.45 * pvRatio, transition: "opacity 1s" }}
              />
              {wakeCount > 0 && !reduced && (
                <circle key={wakeCount} cx={bodyX} cy={bodyY} r="9" fill="none" stroke={COLORS.pv} strokeWidth="1.5" style={once("ring-out", 1800)} />
              )}
            </g>
          ) : (
            <g>
              {STARS.map(([x, y, dur], i) => (
                <circle key={i} cx={x} cy={y} r="1" fill="#dfe6ff" opacity=".5">
                  {!reduced && (
                    <animate attributeName="opacity" values=".15;.8;.15" dur={`${dur}s`} begin={`${-i * 0.7}s`} repeatCount="indefinite" />
                  )}
                </circle>
              ))}
              <circle cx={bodyX} cy={bodyY} r="38" fill="url(#lhMoonGlow)" />
              <rect x={bodyX - 10} y={bodyY - 10} width="20" height="20" fill="#e8ecf5" mask="url(#lhMoonMask)" />
            </g>
          )}
          {/* House */}
          <ellipse
            cx={185 - sunOffset * 0.3}
            cy="252"
            rx={150 + Math.abs(sunOffset) * 0.15}
            ry="34"
            fill="url(#lhShadow)"
            style={{ opacity: sky.day ? 1 : 0.75 }}
          />
          <polygon points="180,242 75,190 75,122 127.5,108 180,174" fill="#262a31" />
          <polygon points="180,242 285,190 285,122 180,174" fill="#1b1e24" />
          <polygon points="180,174 285,122 232.5,56 127.5,108" fill="#14171d" />
          <line x1="127.5" y1="108" x2="232.5" y2="56" stroke="rgba(255,255,255,.09)" strokeWidth="1.5" />
          <line x1="180" y1="174" x2="180" y2="242" stroke="rgba(255,255,255,.05)" strokeWidth="1" />

          {/* Panels: warm up with output, a glint sweeps across while producing */}
          <g transform="matrix(105,-52,-52.5,-66,180,174)">
            <rect x="0.06" y="0.1" width="0.88" height="0.82" fill="#0b111c" />
            {PANEL_CELLS.map(([x, y]) => (
              <g key={`${x}-${y}`}>
                <rect x={x} y={y} width="0.19" height="0.22" fill="#1c2a40" />
                <rect
                  x={x}
                  y={y}
                  width="0.19"
                  height="0.22"
                  fill={PANEL_SHEEN}
                  style={{ opacity: pvRatio * 0.4, transition: "opacity 1.2s ease" }}
                />
              </g>
            ))}
            {pvW >= 100 && !reduced && (
              <g clipPath="url(#lhPanelClip)" style={{ opacity: 0.3 + 0.7 * pvRatio }}>
                <rect x="-0.35" y="0" width="0.3" height="1.1" fill="url(#lhGlint)">
                  <animate attributeName="x" values="-0.35;1.05;1.05" keyTimes="0;0.55;1" dur="6s" repeatCount="indefinite" />
                </rect>
              </g>
            )}
            {wakeCount > 0 && !reduced && (
              <g key={wakeCount} opacity=".35">
              <rect x="0.06" y="0.1" width="0.88" height="0.82" fill={PANEL_SHEEN} style={{ animation: "flash-once 1400ms ease-out both" }} />
            </g>
            )}
          </g>

          {/* Windows: glass by day, lit by night as bright as the load */}
          <g transform="matrix(105,-52,0,-68,180,242)">
            {[0.52, 0.74].map((x) => (
              <g key={x}>
                <rect
                  x={x}
                  y="0.42"
                  width="0.16"
                  height="0.3"
                  style={{
                    fill: sky.day ? "#2b3850" : "#f2e7c4",
                    opacity: sky.day ? 0.9 : 0.3 + 0.65 * loadRatio,
                    transition: "fill 1.5s ease, opacity 1.5s ease",
                  }}
                />
                <rect x={x + 0.075} y="0.42" width="0.012" height="0.3" fill="#1b1e24" />
                <rect x={x} y="0.56" width="0.16" height="0.018" fill="#1b1e24" />
              </g>
            ))}
            <rect x="0.14" y="0" width="0.14" height="0.5" fill="#121419" />
            {/* Inverter */}
            <rect x="0.11" y="0.34" width="0.08" height="0.14" fill="#2b313b" stroke="rgba(255,255,255,.14)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
            <circle cx="0.15" cy="0.44" r="0.012" fill={anyFlow ? COLORS.good : COLORS.dim} />
          </g>

          {/* Battery: liquid level, ripples faster while working, bubbles while charging */}
          <g transform="matrix(-105,-52,0,-68,180,242)">
            <rect x="0.32" y="0.06" width="0.18" height="0.58" fill="#d9dde4" />
            <rect x="0.38" y="0.64" width="0.06" height="0.025" fill="#9aa3b5" />
            <g clipPath="url(#lhBattClip)">
              <g style={{ transform: `translateY(${level}px)`, transition: "transform 1.2s ease" }}>
                <path d={WAVE} style={{ fill: socColor(soc), transition: "fill 1s" }}>
                  {!reduced && (
                    <animateTransform
                      attributeName="transform"
                      type="translate"
                      from="-0.06 0"
                      to="0 0"
                      dur={Math.abs(battW) >= FLOW_MIN_W ? "1.1s" : "3.5s"}
                      repeatCount="indefinite"
                    />
                  )}
                </path>
              </g>
              {charging &&
                !reduced &&
                [0.36, 0.41, 0.46].map((cx, i) => (
                  <circle key={cx} cx={cx} cy="0.08" r="0.009" fill="#fff" opacity=".7">
                    <animate attributeName="cy" from="0.08" to={level} dur="2.2s" begin={`${-i * 0.7}s`} repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0;.8;0" dur="2.2s" begin={`${-i * 0.7}s`} repeatCount="indefinite" />
                  </circle>
                ))}
            </g>
            <rect x="0.32" y="0.06" width="0.03" height="0.58" fill="rgba(0,0,0,.12)" />
          </g>

          {fullCount > 0 && !reduced && (
            <g key={fullCount}>
              <ellipse cx={BATT_TOP.x} cy={BATT_TOP.y + 20} rx="30" ry="38" fill="url(#lhFullGlow)" style={{ animation: "flash-once 1600ms ease-out both" }} />
              {SPARKLES.map(([dx, dy], i) => (
                <g key={i} transform={`translate(${BATT_TOP.x + dx} ${BATT_TOP.y + dy})`}>
                  <path d={SPARKLE_PATH} fill={i % 2 ? "#fff" : COLORS.good} style={once("sparkle", 1200, i * 120)} />
                </g>
              ))}
            </g>
          )}

          {/* Grid pole */}
          {highTier && (
            <g>
              <circle
                cx="318"
                cy="200"
                r="16"
                fill="url(#lhTierGlow)"
                style={reduced ? { opacity: 0.6 } : { animation: "soft-pulse 2.4s ease-in-out infinite", animationPlayState: paused ? "paused" : "running" }}
              />
              <text x="318" y="184" textAnchor="middle" fontSize="9" fontWeight="700" fill={COLORS.gridIn}>
                Tier {scene.tier?.number}
              </text>
            </g>
          )}
          <g stroke="rgba(255,255,255,.2)" strokeWidth="2" strokeLinecap="round">
            <line x1="318" y1="258" x2="318" y2="192" />
            <line x1="306" y1="200" x2="330" y2="200" />
          </g>

          <Flow d={PATH_PV} watts={pvW} color={COLORS.pv} paused={paused} reduced={reduced} />
          <Flow d={PATH_BATT} watts={battW} color={COLORS.batt} paused={paused} reduced={reduced} />
          <Flow d={PATH_LOAD} watts={loadW} color={COLORS.load} paused={paused} reduced={reduced} />
          <Flow
            d={PATH_GRID}
            watts={-gridW}
            color={gridW > 0 ? COLORS.gridIn : COLORS.good}
            paused={paused}
            reduced={reduced}
           
          />
          {/* Junction box where the solar cable meets the eave */}
          <rect x="192.5" y="164" width="6.5" height="5" rx="1" fill="#2b313b" stroke="rgba(255,255,255,.18)" strokeWidth=".8" />
        </svg>

        <Hotspot label={sky.day ? "Solar details" : "Night details"} style={spot(bodyX, bodyY, 46, 46)} active={open === "solar"} onPress={() => toggle("solar")} />
        <Hotspot label="Solar details" style={spot(180, 112, 110, 56)} active={open === "solar"} onPress={() => toggle("solar")} />
        <Hotspot label="Battery details" style={spot(BATT_TOP.x, 200, 34, 52)} active={open === "battery"} onPress={() => toggle("battery")} />
        <Hotspot label="Home details" style={spot(242, 188, 70, 66)} active={open === "home"} onPress={() => toggle("home")} />
        <Hotspot label="Grid details" style={spot(318, 222, 32, 76)} active={open === "grid"} onPress={() => toggle("grid")} />

        {detail && (
          <div
            className="absolute inset-x-1 bottom-1 flex items-start gap-2.5 rounded-xl bg-ink/85 p-2.5 ring-1 ring-white/10 backdrop-blur-md motion-safe:animate-[pop-in_220ms_ease-out_both]"
            aria-live="polite"
          >
            <i className={`fa-solid ${detail.icon} mt-0.5 w-4 text-center text-sm ${detail.tone}`} />
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold leading-snug text-zinc-100">{detail.title}</p>
              {detail.lines.map((line) => (
                <p key={line} className="mt-0.5 text-[11px] tabular-nums text-zinc-400 first-letter:uppercase">
                  {line}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="pointer-events-none absolute left-1 top-1 max-w-[7rem] sm:left-2">
        <div className={`text-[13px] font-bold leading-tight ${scene.stateClass}`}>{scene.state}</div>
      </div>
      {selfPowered && (
        <div className="pointer-events-none absolute right-1 top-1 flex items-center gap-1 rounded-full bg-good/10 px-2 py-0.5 text-[10px] font-bold text-good ring-1 ring-inset ring-good/30 motion-safe:animate-[pop-in_500ms_ease-out_both] sm:right-2">
          <i className="fa-solid fa-leaf" />
          100% solar today
        </div>
      )}

      <div className="mt-1 grid grid-cols-4 gap-1 text-center">
        <Stat label="Solar" value={fmtPower(pvShown)} className="text-pv" active={open === "solar"} onPress={() => toggle("solar")} />
        <Stat label="Home" value={fmtPower(loadShown)} className="text-load" active={open === "home"} onPress={() => toggle("home")} />
        <Stat
          label="Battery"
          note={`${Math.round(soc)}%`}
          value={fmtPower(battShown)}
          className="text-batt"
          active={open === "battery"}
          onPress={() => toggle("battery")}
        />
        <Stat
          label={gridW < -FLOW_MIN_W ? "Export" : "Grid"}
          value={fmtPower(gridShown)}
          className={gridW > FLOW_MIN_W ? "text-grid-in" : gridW < -FLOW_MIN_W ? "text-good" : "text-zinc-400"}
          active={open === "grid"}
          onPress={() => toggle("grid")}
        />
      </div>
    </div>
  );
}

function Hotspot({ label, style, active, onPress }: { label: string; style: CSSProperties; active: boolean; onPress: () => void }) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-expanded={active}
      style={style}
      onClick={(event) => {
        event.stopPropagation();
        onPress();
      }}
      className="absolute cursor-pointer rounded-2xl outline-none focus-visible:ring-1 focus-visible:ring-white/40"
    />
  );
}

function Stat({
  label,
  note,
  value,
  className,
  active,
  onPress,
}: {
  label: string;
  note?: string;
  value: string;
  className: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <button
      type="button"
      aria-expanded={active}
      onClick={onPress}
      className={`rounded-xl py-1 transition-colors ${active ? "bg-white/[0.06]" : "hover:bg-white/[0.03]"}`}
    >
      <p className={`text-sm font-bold tabular-nums ${className}`}>{value}</p>
      <p className="mt-0.5 text-[10px] font-bold uppercase tracking-widest text-zinc-500">{label}</p>
      {note && <p className="text-[10px] font-semibold tabular-nums text-zinc-400">{note}</p>}
    </button>
  );
}
