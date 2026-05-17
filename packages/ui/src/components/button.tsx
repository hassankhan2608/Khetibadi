import type { ButtonHTMLAttributes } from "react";

import { cn } from "../lib/cn.js";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
}

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-[#2f5d3a] text-[#fffaf0] shadow-[#2f5d3a]/20 hover:bg-[#244b2f] focus-visible:ring-[#2f5d3a]",
  secondary:
    "border border-[#d8c4a5] bg-[#fffaf0] text-[#3f2f1f] shadow-[#7a4e2d]/10 hover:bg-[#f5ebd7]",
  ghost: "bg-transparent text-[#5f4a33] hover:bg-[#efe3d1]/70",
  danger: "bg-[#9b2f22] text-[#fffaf0] hover:bg-[#7e261c] focus-visible:ring-[#9b2f22]",
};

export function Button({
  className,
  variant = "primary",
  loading = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60",
        variants[variant],
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? "Loading…" : children}
    </button>
  );
}
