import type { InputHTMLAttributes, LabelHTMLAttributes, TextareaHTMLAttributes } from "react";

import { cn } from "../lib/cn.js";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}
export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {}
export interface LabelProps extends LabelHTMLAttributes<HTMLLabelElement> {}

export function Label({ className, ...props }: LabelProps) {
  return <label className={cn("text-sm font-semibold text-[#5f4a33]", className)} {...props} />;
}

export function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 disabled:cursor-not-allowed disabled:bg-slate-50",
        "w-full rounded-xl border-[#d8c4a5] bg-[#fffaf0] text-[#2d2217] shadow-[#7a4e2d]/5 placeholder:text-[#9b8464] focus:border-[#2f5d3a] focus:ring-[#2f5d3a]/15 disabled:bg-[#f2e6cf]",
        className,
      )}
      {...props}
    />
  );
}

export function Textarea({ className, ...props }: TextareaProps) {
  return (
    <textarea
      className={cn(
        "min-h-28 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 disabled:cursor-not-allowed disabled:bg-slate-50",
        "min-h-28 w-full rounded-xl border-[#d8c4a5] bg-[#fffaf0] text-[#2d2217] shadow-[#7a4e2d]/5 placeholder:text-[#9b8464] focus:border-[#2f5d3a] focus:ring-[#2f5d3a]/15 disabled:bg-[#f2e6cf]",
        className,
      )}
      {...props}
    />
  );
}
