/**
 * What the wealth charts draw (F-WLT-6), read from the wealth matrix. Display only: amounts
 * become numbers for the geometry, the matrix keeps the exact ones.
 */
import type { WealthMatrixOut } from "../api/generated";

/** The holder of the household's joint lines. */
export const JOINT = "joint";

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

/** The last month's assets by category (the matrix's order) then line; empty ones left out. */
export function allocation(m: WealthMatrixOut): { total: number; categories: CategorySlice[] } {
  const last = lastIndex(m);
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

/** `name` is null for the joint holder: the caller names it in the user's language. */
export type Holder = { key: string; name: string | null };

export type HoldingColumn = {
  id: string;
  name: string;
  colour: string;
  value: number;
  /** Of gross assets: the column's width. */
  share: number;
  /** In the holders' order; `share` is of the column. */
  parts: { holder: string; value: number; share: number }[];
};

/** Each asset category split by who holds it: the viewer first, other members, joint last. */
export function holdings(
  m: WealthMatrixOut,
  viewerId: string,
): { holders: Holder[]; columns: HoldingColumn[] } {
  const last = lastIndex(m);
  const names = new Map<string, string>();
  const columns = allocation(m).categories.map((slice) => {
    const category = m.categories.find((c) => c.id === slice.id);
    const byHolder = new Map<string, number>();
    for (const l of category?.lines ?? []) {
      const value = Number(l.cells[last]?.amount ?? 0);
      if (value <= 0) continue;
      const holder = l.visibility === "joint" ? JOINT : l.owner_id;
      if (holder !== JOINT) names.set(holder, l.owner_name);
      byHolder.set(holder, (byHolder.get(holder) ?? 0) + value);
    }
    return { slice, byHolder };
  });
  const rank = (key: string) => (key === viewerId ? 0 : key === JOINT ? 2 : 1);
  const keys = [...new Set(columns.flatMap((c) => [...c.byHolder.keys()]))].sort(
    (a, b) => rank(a) - rank(b) || (names.get(a) ?? "").localeCompare(names.get(b) ?? ""),
  );
  return {
    holders: keys.map((key) => ({ key, name: key === JOINT ? null : (names.get(key) ?? null) })),
    columns: columns.map(({ slice, byHolder }) => ({
      id: slice.id,
      name: slice.name,
      colour: slice.colour,
      value: slice.value,
      share: slice.share,
      parts: keys
        .filter((key) => byHolder.has(key))
        .map((key) => {
          const value = byHolder.get(key) ?? 0;
          return { holder: key, value, share: value / slice.value };
        }),
    })),
  };
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
