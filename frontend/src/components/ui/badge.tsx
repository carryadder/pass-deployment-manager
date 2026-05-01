import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const toneClasses: Record<string, string> = {
  success: "bg-moss/20 text-slate",
  warning: "bg-coral/15 text-ink",
  info: "bg-cyan/20 text-slate",
  neutral: "bg-ink/8 text-ink/80",
};

export function Badge({
  className,
  tone = "neutral",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: keyof typeof toneClasses }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]",
        toneClasses[tone],
        className,
      )}
      {...props}
    />
  );
}
