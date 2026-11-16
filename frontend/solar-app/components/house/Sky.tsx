"use client";

interface Tint {
  color: string;
  opacity: number;
}

function skyTint(day: boolean, progress: number): Tint {
  if (!day) return { color: "#3a4f9a", opacity: 0.16 };
  if (progress < 0.1) return { color: "#ff9f68", opacity: 0.2 };
  if (progress > 0.9) return { color: "#c27bff", opacity: 0.2 };
  return { color: "#5b8cff", opacity: 0.13 };
}

/** Warm light along the horizon right after sunrise and before sunset. */
function horizonGlow(day: boolean, progress: number): number {
  if (!day) return 0;
  const edge = Math.min(progress, 1 - progress);
  return Math.max(0, 1 - edge / 0.12);
}

// Sky color for the time of day: dawn orange, day blue, dusk violet, night indigo.
export function SkyBackdrop({ day, progress, sunX }: { day: boolean; progress: number; sunX: number }) {
  const tint = skyTint(day, progress);
  const glow = horizonGlow(day, progress);
  return (
    <g>
      <defs>
        <radialGradient id="lhSkyTint">
          <stop offset="0%" style={{ stopColor: tint.color, stopOpacity: tint.opacity, transition: "stop-color 2s, stop-opacity 2s" }} />
          <stop offset="100%" style={{ stopColor: tint.color, stopOpacity: 0, transition: "stop-color 2s" }} />
        </radialGradient>
        <radialGradient id="lhHorizon">
          <stop offset="0%" stopColor="#ff9a55" stopOpacity=".35" />
          <stop offset="100%" stopColor="#ff9a55" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx="180" cy="110" rx="200" ry="135" fill="url(#lhSkyTint)" />
      <ellipse cx={sunX} cy="150" rx="120" ry="46" fill="url(#lhHorizon)" style={{ opacity: glow, transition: "opacity 2s" }} />
    </g>
  );
}
