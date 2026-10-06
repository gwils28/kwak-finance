/** Months as the API writes them: "2026-03". */

import { dateFormat } from "./locale";

const MONTH_LABEL: Intl.DateTimeFormatOptions = { month: "short", year: "numeric" };

export function thisMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export function shiftMonth(month: string, delta: number): string {
  const [year, m] = month.split("-").map(Number) as [number, number];
  const index = year * 12 + (m - 1) + delta;
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`;
}

/** "2026-03" -> "Mar 2026" (en) or "mars 2026" (fr). */
export function monthLabel(month: string): string {
  const [year, m] = month.split("-").map(Number) as [number, number];
  return dateFormat(MONTH_LABEL).format(new Date(year, m - 1, 1));
}

export function daysInMonth(month: string): number {
  const [year, m] = month.split("-").map(Number) as [number, number];
  return new Date(year, m, 0).getDate();
}

/** First and last day, as the transactions filters expect them. */
export function monthBounds(month: string): { from: string; to: string } {
  return {
    from: `${month}-01`,
    to: `${month}-${String(daysInMonth(month)).padStart(2, "0")}`,
  };
}
