import type { ComponentPropsWithoutRef } from "react";

const ACCENTS = {
  pv: "border-t-pv/20",
  load: "border-t-load/20",
  good: "border-t-good/25",
  warn: "border-t-grid-in/25",
};

interface CardProps extends ComponentPropsWithoutRef<"section"> {
  accent?: keyof typeof ACCENTS;
  /** Padding classes; pass "" for a card that sets its own size. */
  pad?: string;
}

export default function Card({ accent, pad = "p-3 sm:p-4", className, ...props }: CardProps) {
  const classes = [
    "rounded-[22px] border border-white/10 bg-card/90 shadow-2xl backdrop-blur-xl",
    accent && ACCENTS[accent],
    pad,
    className,
  ];
  return <section className={classes.filter(Boolean).join(" ")} {...props} />;
}
