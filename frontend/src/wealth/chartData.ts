/**
 * What the wealth charts draw (F-WLT-6), read from the wealth matrix. Display only: amounts
 * become numbers for the geometry, the matrix keeps the exact ones.
 */
import type { WealthMatrixOut } from "../api/generated";

export type LineSlice = { id: string; name: string; value: number; share: number };

export type CategorySlice = {
  id: string;
  name: string;
  colour: string;
  value: number;
  /** Of gross assets. */
  share: number;
  /** From the largest. */
  lines: LineSlice[];
};

const lastIndex = (m: WealthMatrixOut) => m.months.length - 1;

export type Allocation = { total: number; categories: CategorySlice[] };

/**
 * A month's assets (the last one shown by default) by category, in the matrix's order, then
 * line; empty ones left out.
 */
export function allocation(m: WealthMatrixOut, month = lastIndex(m)): Allocation {
  const last = month;
  const total = Number(m.gross[last] ?? 0);
  if (total <= 0) return { total: 0, categories: [] };
  const categories = m.categories
    .filter((c) => c.kind === "asset" && Number(c.subtotals[last] ?? 0) > 0)
    .map((c) => {
      const value = Number(c.subtotals[last]);
      const lines = c.lines
        .map((l) => ({ id: l.id, name: l.name, value: Number(l.cells[last]?.amount ?? 0) }))
        .filter((l) => l.value > 0)
        .sort((a, b) => b.value - a.value)
        .map((l) => ({ ...l, share: l.value / total }));
      return { id: c.id, name: c.name, colour: c.colour, value, share: value / total, lines };
    });
  return { total, categories };
}

export type HistoryRow = { month: string; net: number } & Record<string, number | string>;

/** One row per month: each category that ever holds something (debts below zero), net worth. */
export function history(m: WealthMatrixOut): HistoryRow[] {
  const held = m.categories.filter((c) => c.subtotals.some((v) => Number(v) !== 0));
  return m.months.map((month, i) => {
    const row: HistoryRow = { month, net: Number(m.net[i] ?? 0) };
    for (const c of held) {
      const value = Number(c.subtotals[i] ?? 0);
      row[c.id] = c.kind === "debt" ? -value : value;
    }
    return row;
  });
}

export type BridgeStep = {
  /** "start", "end", or the category's id. */
  key: string;
  kind: "start" | "up" | "down" | "end";
  from: number;
  to: number;
  delta: number;
};

/**
 * From the first month's net worth to the last's, one step per category that moved; a debt
 * repaid lifts net worth. Null with a single month: nothing to compare.
 */
export function bridge(m: WealthMatrixOut): BridgeStep[] | null {
  const last = lastIndex(m);
  if (last < 1) return null;
  const start = Number(m.net[0] ?? 0);
  const steps: BridgeStep[] = [{ key: "start", kind: "start", from: 0, to: start, delta: start }];
  let running = start;
  for (const c of m.categories) {
    const moved = Number(c.subtotals[last] ?? 0) - Number(c.subtotals[0] ?? 0);
    const delta = c.kind === "debt" ? -moved : moved;
    if (delta === 0) continue;
    steps.push({
      key: c.id,
      kind: delta > 0 ? "up" : "down",
      from: running,
      to: running + delta,
      delta,
    });
    running += delta;
  }
  const end = Number(m.net[last] ?? 0);
  steps.push({ key: "end", kind: "end", from: 0, to: end, delta: end });
  return steps;
}

export type NetWorthPoint = { month: string; net: number };

/**
 * Net worth each month, the assets of the categories in `without` taken off (the main home,
 * say, which can flatten every other move).
 */
export function netWorth(
  m: WealthMatrixOut,
  without: ReadonlySet<string> = new Set(),
): NetWorthPoint[] {
  const off = m.categories.filter((c) => c.kind === "asset" && without.has(c.id));
  return m.months.map((month, i) => ({
    month,
    net: off.reduce((net, c) => net - Number(c.subtotals[i] ?? 0), Number(m.net[i] ?? 0)),
  }));
}

/** 1, 2 or 5 times a power of ten, the closest above `raw`. */
function roundStep(raw: number): number {
  const power = 10 ** Math.floor(Math.log10(raw));
  const unit = raw / power;
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 5 ? 5 : 10) * power;
}

export type Axis = { domain: [number, number]; ticks: number[] };

/**
 * An axis fitted to the values, not to zero, in about four round steps with a margin: a
 * change of a few percent stays visible.
 */
export function fittedAxis(values: number[]): Axis {
  if (values.length === 0) return { domain: [0, 1], ticks: [0, 1] };
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = high - low || Math.abs(high) / 10 || 1;
  const step = roundStep(span / 4);
  const margin = step / 4;
  const start = Math.floor((low - margin) / step) * step;
  const end = Math.ceil((high + margin) / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= end + step / 2; v += step) ticks.push(Math.round(v * 100) / 100);
  return { domain: [start, end], ticks };
}

/**
 * The categories the filter offers: those holding something over the months shown, those left
 * out (to tick them again), and those the matrix does not list; every one before it loads.
 */
export function shownInFilter<T extends { id: string }>(
  categories: T[],
  m: WealthMatrixOut | undefined,
  excluded: string[],
): T[] {
  if (!m) return categories;
  const listed = new Map(m.categories.map((c) => [c.id, c]));
  return categories.filter((c) => {
    const row = listed.get(c.id);
    return !row || excluded.includes(c.id) || row.subtotals.some((v) => Number(v) !== 0);
  });
}
