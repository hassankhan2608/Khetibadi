import type { HTMLAttributes } from "react";

import { cn } from "../lib/cn.js";

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {}

export function Skeleton({ className, ...props }: SkeletonProps) {
  return <div className={cn("animate-pulse rounded-xl bg-slate-200", className)} {...props} />;
}
