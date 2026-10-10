/** Budget plans over calendar periods: "2027" (year), "2027-S1" (semester), "2027-Q3" (quarter). */

import type { PeriodKind, PlanOut } from "../api/generated";
import { daysInMonth, shiftMonth } from "./months";

export type Period = { kind: PeriodKind; year: number; number: number };

const MONTHS: Record<PeriodKind, number> = { year: 12, semester: 6, quarter: 3 };
const LETTER: Record<"semester" | "quarter", string> = { semester: "S", quarter: "Q" };

export function parsePeriod(text: string): Period {
  const [year, part] = text.split("-") as [string, string | undefined];
  if (!part) return { kind: "year", year: Number(year), number: 1 };
  return {
    kind: part.startsWith("S") ? "semester" : "quarter",
    year: Number(year),
    number: Number(part.slice(1)),
  };
}

export function periodText({ kind, year, number }: Period): string {
  return kind === "year" ? String(year) : `${year}-${LETTER[kind]}${number}`;
}

/** How many periods of this kind make a year: 1, 2 or 4. */
export function periodsPerYear(kind: PeriodKind): number {
  return 12 / MONTHS[kind];
}

export function periodStart({ kind, year, number }: Period): string {
  return shiftMonth(`${year}-01`, (number - 1) * MONTHS[kind]);
}

/** The period of this kind holding `month`. */
export function periodContaining(kind: PeriodKind, month: string): Period {
  const [year, m] = month.split("-").map(Number) as [number, number];
  return { kind, year, number: Math.floor((m - 1) / MONTHS[kind]) + 1 };
}

export function nextPeriod(period: Period): Period {
  const last = periodsPerYear(period.kind);
  return period.number < last
    ? { ...period, number: period.number + 1 }
    : { ...period, year: period.year + 1, number: 1 };
}

/** Months from `start` to `end`, both "YYYY-MM" and included. */
export function monthsBetween(start: string, end: string): string[] {
  const months = [];
  for (let m = start; m <= end; m = shiftMonth(m, 1)) months.push(m);
  return months;
}

export function covering(plans: PlanOut[], month: string): PlanOut | undefined {
  return plans.find((p) => p.start <= month && month <= p.end);
}

/** The plan to show first: the one covering this month, else the latest. */
export function defaultPlan(plans: PlanOut[], month: string): PlanOut | undefined {
  return covering(plans, month) ?? plans.at(-1);
}

/**
 * The period a new plan most likely covers: the one after the latest plan, of the same kind,
 * else this month's quarter.
 */
export function suggestedPeriod(plans: PlanOut[], month: string): Period {
  const latest = plans.at(-1);
  if (!latest) return periodContaining("quarter", month);
  const period = parsePeriod(latest.period);
  // A plan closed early leaves the rest of its period to its replacement, listed after it.
  return latest.end < month ? periodContaining(period.kind, month) : nextPeriod(period);
}

/** The last day the plan's targets can change: the end of its first month, "YYYY-MM-DD". */
export function editableUntil(plan: PlanOut): string {
  return `${plan.start}-${String(daysInMonth(plan.start)).padStart(2, "0")}`;
}

/** Monthly targets by category; a parent without its own target gets its children's sum. */
export type PlanTarget = { amount: string; fromChildren: boolean };

// API amounts always have two decimals: "400.00" -> 40000 cents, summed as whole numbers.
const cents = (amount: string) => Number(amount.replace(".", ""));
const euros = (total: number) =>
  `${Math.floor(total / 100)}.${String(total % 100).padStart(2, "0")}`; // targets are >= 0

export function planTargets(
  plan: PlanOut,
  categories: { category_id: string | null; parent_id: string | null; level: number }[],
): { byCategory: Map<string, PlanTarget>; total: string | null } {
  const own = new Map(plan.targets.map((t) => [t.category_id, t.amount]));
  const byCategory = new Map<string, PlanTarget>();
  let total = 0;
  let any = false;
  for (const row of categories) {
    if (!row.category_id) continue;
    const amount = own.get(row.category_id);
    if (amount !== undefined) {
      byCategory.set(row.category_id, { amount, fromChildren: false });
    } else if (row.level === 0) {
      const children = categories
        .map((c) =>
          c.parent_id === row.category_id && c.category_id ? own.get(c.category_id) : undefined,
        )
        .filter((a): a is string => a !== undefined);
      if (children.length > 0)
        byCategory.set(row.category_id, {
          amount: euros(children.reduce((sum, a) => sum + cents(a), 0)),
          fromChildren: true,
        });
    }
    const top = row.level === 0 ? byCategory.get(row.category_id) : undefined;
    if (top) {
      total += cents(top.amount);
      any = true;
    }
  }
  return { byCategory, total: any ? euros(total) : null };
}
