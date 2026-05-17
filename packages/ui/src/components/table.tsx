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
  return <thead className={cn("border-b border-[#d8c4a5]", className)} {...props} />;
}

export function TableBody({ className, ...props }: TableSectionProps) {
  return <tbody className={cn("divide-y divide-[#eadbc2]", className)} {...props} />;
}

export function TableRow({ className, ...props }: TableRowProps) {
  return <tr className={cn("transition hover:bg-[#f7eddc]", className)} {...props} />;
}

export function TableHead({ className, ...props }: TableHeadProps) {
  return <th className={cn("px-4 py-3 text-left font-bold text-[#5f4a33]", className)} {...props} />;
}

export function TableCell({ className, ...props }: TableCellProps) {
  return <td className={cn("px-4 py-3 text-[#5f4a33]", className)} {...props} />;
}
