import type { HTMLAttributes } from "react";

import { cn } from "../lib/cn.js";

export type BadgeTone = "green" | "amber" | "red" | "blue" | "slate";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

const tones: Record<BadgeTone, string> = {
  green: "bg-[#e3eadb] text-[#2f5d3a] ring-[#2f5d3a]/20",
  amber: "bg-[#f3dfb4] text-[#7a4e2d] ring-[#b87924]/30",
  red: "bg-[#f4d8ce] text-[#8a2f22] ring-[#8a2f22]/20",
  blue: "bg-[#dbe9df] text-[#315a51] ring-[#315a51]/20",
  slate: "bg-[#efe3d1] text-[#5f4a33] ring-[#7a4e2d]/15",
};

export function Badge({ className, tone = "slate", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
