"use client";

import { useEffect, useState } from "react";

function formatClock(ms: number): string {
  return new Date(ms).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatAgo(seconds: number): string {
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

export default function UpdatedAgo({ iso }: { iso?: string }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  if (!iso) return null;
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return null;

  const seconds = Math.max(0, Math.round((now - then) / 1000));
  const clock = formatClock(then);

  return (
    <time className="text-[11px] font-semibold tabular-nums text-zinc-500" dateTime={iso} title={`Updated ${clock}`}>
      Updated {formatAgo(seconds)}
    </time>
  );
}
