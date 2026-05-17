import type { HTMLAttributes } from "react";

import { cn } from "../lib/cn.js";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {}

export function Card({ className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-[1.6rem] border border-[#dbc7a8] bg-[#fffaf0]/95 shadow-[0_18px_55px_rgba(65,44,24,0.08)]",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: CardProps) {
  return <div className={cn("border-b border-[#e7d8bf] p-5", className)} {...props} />;
}

export function CardTitle({ className, ...props }: CardProps) {
  return <div className={cn("text-lg font-bold tracking-tight text-[#2d2217]", className)} {...props} />;
}

export function CardContent({ className, ...props }: CardProps) {
  return <div className={cn("p-5", className)} {...props} />;
}
