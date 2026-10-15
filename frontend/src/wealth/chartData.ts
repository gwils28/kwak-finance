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

export type Rect = { x: number; y: number; w: number; h: number };

/**
 * Squarified treemap (Bruls, Huizing, van Wijk): tiles `rect` with one rectangle per value, in
 * the given order (largest first reads best), each as close to a square as the row allows.
 */
export function squarify(values: number[], rect: Rect): Rect[] {
  const total = values.reduce((sum, v) => sum + v, 0);
  if (values.length === 0 || total <= 0) return values.map(() => ({ ...rect, w: 0, h: 0 }));
  const scale = (rect.w * rect.h) / total;
  const areas = values.map((v) => v * scale);
  const out: Rect[] = [];
  let free = { ...rect };
  let start = 0;
  const worst = (row: number[], side: number) => {
    const sum = row.reduce((a, b) => a + b, 0);
    const max = Math.max(...row);
    const min = Math.min(...row);
    return Math.max((side * side * max) / (sum * sum), (sum * sum) / (side * side * min));
  };
  while (start < areas.length) {
    const side = Math.min(free.w, free.h);
    let end = start + 1;
    while (
      end < areas.length &&
      worst(areas.slice(start, end + 1), side) <= worst(areas.slice(start, end), side)
    )
      end += 1;
    const row = areas.slice(start, end);
    const sum = row.reduce((a, b) => a + b, 0);
    if (free.w >= free.h) {
      // A column along the left side.
      const width = free.h > 0 ? sum / free.h : 0;
      let y = free.y;
      for (const a of row) {
        const h = width > 0 ? a / width : 0;
        out.push({ x: free.x, y, w: width, h });
        y += h;
      }
      free = { x: free.x + width, y: free.y, w: free.w - width, h: free.h };
    } else {
      // A row along the top.
      const height = free.w > 0 ? sum / free.w : 0;
      let x = free.x;
      for (const a of row) {
        const w = height > 0 ? a / height : 0;
        out.push({ x, y: free.y, w, h: height });
        x += w;
      }
      free = { x: free.x, y: free.y + height, w: free.w, h: free.h - height };
    }
    start = end;
  }
  return out;
}

export type MosaicTile = { category: CategorySlice; rect: Rect };

/** The allocation as a mosaic: one tile per category, from the largest. */
export function mosaic({ categories }: Allocation, rect: Rect): MosaicTile[] {
  const sorted = [...categories].sort((a, b) => b.value - a.value);
  const tiles = squarify(
    sorted.map((c) => c.value),
    rect,
  );
  return sorted.map((category, i) => ({ category, rect: tiles[i] as Rect }));
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
