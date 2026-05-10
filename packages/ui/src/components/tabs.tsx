import type { ButtonHTMLAttributes, HTMLAttributes } from "react";

import { cn } from "../lib/cn.js";

export interface TabsProps extends HTMLAttributes<HTMLDivElement> {}
export interface TabButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

export function Tabs({ className, ...props }: TabsProps) {
  return <div className={cn("space-y-4", className)} {...props} />;
}

export function TabList({ className, ...props }: TabsProps) {
  return <div className={cn("inline-flex rounded-xl bg-slate-100 p-1", className)} role="tablist" {...props} />;
}

export function TabButton({ className, active = false, ...props }: TabButtonProps) {
  return (
    <button
      className={cn(
        "rounded-lg px-3 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500",
        active ? "bg-white text-emerald-700 shadow-sm" : "text-slate-600 hover:text-slate-900",
        className,
      )}
      role="tab"
      aria-selected={active}
      {...props}
    />
  );
}

export function TabPanel({ className, ...props }: TabsProps) {
  return <div className={cn("outline-none", className)} role="tabpanel" {...props} />;
}
