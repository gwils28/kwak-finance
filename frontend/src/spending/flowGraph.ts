/** The money flows' graph (F-DSH-2): what comes in on the left, what goes out on the right. */

export type FlowRole = "income" | "spent" | "overspent" | "saved" | "deficit" | "other";

export type FlowEntry = {
  key: string;
  label: string;
  side: "in" | "out";
  role: FlowRole;
  amount: number;
  over: boolean;
};

export type FlowNode = { key: string; label: string; role: FlowRole | "hub"; amount: number };
export type FlowLink = { source: number; target: number; value: number; role: FlowRole };

/** From this share of the money in, one source would draw a near plain band into the hub. */
const DOMINANT = 0.9;

/**
 * The sources flow into a hub, which flows out to the uses. A single source is the hub itself:
 * a band from it to a hub of the same size would only draw a plain rectangle. When one source
 * brings 90 % or more, the hub stands alone for the same reason (the totals list the sources).
 */
export function flowGraph(
  left: FlowEntry[],
  right: FlowEntry[],
  hubLabel: string,
): { nodes: FlowNode[]; links: FlowLink[]; hub: number } {
  const [only] = left;
  if (left.length === 1 && only) {
    return {
      nodes: [only, ...right],
      links: right.map((e, i) => ({ source: 0, target: 1 + i, value: e.amount, role: e.role })),
      hub: 0,
    };
  }
  const total = left.reduce((sum, e) => sum + e.amount, 0);
  if (total > 0 && left.some((e) => e.amount >= DOMINANT * total)) {
    return {
      nodes: [{ key: "hub", label: hubLabel, role: "hub", amount: total }, ...right],
      links: right.map((e, i) => ({ source: 0, target: 1 + i, value: e.amount, role: e.role })),
      hub: 0,
    };
  }
  const hub = left.length;
  return {
    nodes: [...left, { key: "hub", label: hubLabel, role: "hub", amount: total }, ...right],
    links: [
      ...left.map((e, i) => ({ source: i, target: hub, value: e.amount, role: e.role })),
      ...right.map((e, i) => ({ source: hub, target: hub + 1 + i, value: e.amount, role: e.role })),
    ],
    hub,
  };
}
