import type { HTMLAttributes, ThHTMLAttributes, TdHTMLAttributes } from "react";

import { cn } from "../lib/cn.js";

export interface TableProps extends HTMLAttributes<HTMLTableElement> {}
export interface TableSectionProps extends HTMLAttributes<HTMLTableSectionElement> {}
export interface TableRowProps extends HTMLAttributes<HTMLTableRowElement> {}
export interface TableHeadProps extends ThHTMLAttributes<HTMLTableCellElement> {}
export interface TableCellProps extends TdHTMLAttributes<HTMLTableCellElement> {}

export function Table({ className, ...props }: TableProps) {
  return <table className={cn("w-full caption-bottom text-sm", className)} {...props} />;
}

export function TableHeader({ className, ...props }: TableSectionProps) {
  return <thead className={cn("border-b border-slate-200", className)} {...props} />;
}

export function TableBody({ className, ...props }: TableSectionProps) {
  return <tbody className={cn("divide-y divide-slate-100", className)} {...props} />;
}

export function TableRow({ className, ...props }: TableRowProps) {
  return <tr className={cn("transition hover:bg-slate-50", className)} {...props} />;
}

export function TableHead({ className, ...props }: TableHeadProps) {
  return <th className={cn("px-4 py-3 text-left font-semibold text-slate-700", className)} {...props} />;
}

export function TableCell({ className, ...props }: TableCellProps) {
  return <td className={cn("px-4 py-3 text-slate-700", className)} {...props} />;
}
