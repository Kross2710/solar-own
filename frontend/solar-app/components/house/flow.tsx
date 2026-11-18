"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";

// Below this a flow is treated as off (inverter standby, meter noise).
export const FLOW_MIN_W = 20;

function subscribeMotion(onChange: () => void) {
  const query = window.matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeMotion,
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => false,
  );
}

function subscribeVisibility(onChange: () => void) {
  document.addEventListener("visibilitychange", onChange);
  return () => document.removeEventListener("visibilitychange", onChange);
}

export function usePageVisible(): boolean {
  return useSyncExternalStore(subscribeVisibility, () => !document.hidden, () => true);
}

/** Pauses SMIL animations inside the svg while the tab is hidden. */
export function useSvgPause(visible: boolean) {
  const ref = useRef<SVGSVGElement>(null);
  useEffect(() => {
    const svg = ref.current;
    if (!svg) return;
    if (visible) svg.unpauseAnimations();
    else svg.pauseAnimations();
  }, [visible]);
  return ref;
}

/** Eases a number toward its new value instead of jumping on every poll. */
export function useTween(target: number, ms = 700): number {
  const reduced = useReducedMotion();
  const [value, setValue] = useState(target);
  const current = useRef(target);

  useEffect(() => {
    const from = current.current;
    const start = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const t = reduced ? 1 : Math.min(1, (now - start) / ms);
      const next = from + (target - from) * (1 - (1 - t) ** 3);
      current.current = next;
      setValue(next);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, ms, reduced]);

  return value;
}

export function fmtPower(watts: number): string {
  const abs = Math.abs(watts);
  return abs >= 1000 ? `${(abs / 1000).toFixed(2)} kW` : `${Math.round(abs)} W`;
}

// The pulse is a 16-unit dash in a 60-unit period; the keyframes travel one period.
const PULSE_DASH = "16 44";
const PULSE_TRAVEL = 60;

interface FlowProps {
  d: string;
  /** Signed watts: positive runs along the path, negative against it. */
  watts: number;
  color: string;
  paused: boolean;
  reduced: boolean;
}

// One wire: the cable lights up in its color while power flows, and a pulse of light
// travels through it, faster and thicker with more power.
export function Flow({ d, watts, color, paused, reduced }: FlowProps) {
  const kw = Math.abs(watts) / 1000;
  const on = Math.abs(watts) >= FLOW_MIN_W;
  const speed = 14 + 12 * Math.min(kw, 8); // user units per second
  const width = 2.2 + Math.min(kw, 6) * 0.45;

  return (
    <g>
      <path d={d} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="2.5" strokeLinecap="round" />
      <g style={{ opacity: on ? 1 : 0, transition: "opacity 700ms ease" }}>
        <path d={d} fill="none" stroke={color} strokeWidth={width + 5} strokeLinecap="round" opacity=".16" />
        <path d={d} fill="none" stroke={color} strokeWidth={width * 0.7} strokeLinecap="round" opacity=".45" />
        {!reduced && (
          <path
            d={d}
            fill="none"
            stroke={color}
            strokeWidth={width + 1}
            strokeLinecap="round"
            strokeDasharray={PULSE_DASH}
            style={{
              animationName: "flow-pulse",
              animationDuration: `${PULSE_TRAVEL / speed}s`,
              animationTimingFunction: "linear",
              animationIterationCount: "infinite",
              animationDirection: watts < 0 ? "reverse" : "normal",
              animationPlayState: paused ? "paused" : "running",
            }}
          />
        )}
      </g>
    </g>
  );
}

export interface SceneData {
  pvW: number;
  loadW: number;
  /** Positive while charging. */
  battW: number;
  /** Positive while importing from the grid. */
  gridW: number;
  soc: number;
  capacityKw: number;
  lat: number;
  lon: number;
  now: Date;
  state: string;
  stateClass: string;
  /** Usual solar output at this time of day, W (30-day hourly profile). */
  typicalPvW?: number | null;
  todayKwh?: number | null;
  expectedKwh?: number | null;
  tomorrowKwh?: number | null;
  consKwh?: number | null;
  buyKwh?: number | null;
  reservePct?: number | null;
  /** Current EVN tier, 1-based, with its price in đ/kWh. */
  tier?: { number: number; price: number | null } | null;
  battery?: { title: string; detail: string } | null;
}

/** Remembers how many times `active` has switched on, to replay one-shot animations. */
export function useRisingEdge(active: boolean): number {
  const [prev, setPrev] = useState(active);
  const [count, setCount] = useState(0);
  if (active !== prev) {
    setPrev(active);
    if (active) setCount(count + 1);
  }
  return count;
}
